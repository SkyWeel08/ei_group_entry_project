from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pdfplumber

from eilink_pipeline.config import PipelineConfig
from eilink_pipeline.text_utils import canonical_label

EXISTING_TABLE_NAMES = {
    canonical_label("Operations"),
    canonical_label("Equipment Failure"),
    canonical_label("Equipment Failure Information"),
    canonical_label("Drilling Fluid"),
}

NOISE_TABLE_TITLES = {
    canonical_label("Summary report"),
    canonical_label("Comment"),
}

CASING_TABLE_CANONICAL = canonical_label("Casing Liner Tubing")


def _dedupe_doubled_token(token: str) -> str:
    value = token.strip()
    if len(value) >= 2 and len(value) % 2 == 0 and all(value[i] == value[i + 1] for i in range(0, len(value), 2)):
        return value[::2]
    return value


def _normalize_cell(value: object) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).replace("\n", " ").split())
    if not text:
        return ""
    parts = [_dedupe_doubled_token(token) for token in text.split(" ")]
    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def _line_above_table(words: list[dict], table_top: float, max_gap: float = 20.0) -> str:
    above = [word for word in words if word["bottom"] <= table_top and table_top - word["bottom"] <= max_gap]
    if not above:
        return ""

    by_line: dict[float, list[dict]] = {}
    for word in above:
        key = round(float(word["top"]), 1)
        by_line.setdefault(key, []).append(word)
    nearest = max(by_line)
    ordered = sorted(by_line[nearest], key=lambda item: item["x0"])
    return _normalize_cell(" ".join(word["text"] for word in ordered))


def _is_useless_title(title: str) -> bool:
    canonical = canonical_label(title)
    if not canonical:
        return True
    if canonical in NOISE_TABLE_TITLES:
        return True
    if canonical in EXISTING_TABLE_NAMES:
        return True
    if canonical.startswith("wellbore "):
        return True
    return False


def _row_is_title(row: list[str], table_title: str) -> bool:
    non_empty = [value for value in row if value]
    if len(non_empty) != 1:
        return False
    cell = canonical_label(non_empty[0])
    title = canonical_label(table_title)
    if not title:
        return False
    return cell == title or cell.startswith(title)


def _unique_headers(header_row: list[str]) -> list[str]:
    headers = []
    seen: dict[str, int] = {}
    for idx, raw in enumerate(header_row, start=1):
        base = _normalize_cell(raw)
        if not base:
            base = f"column_{idx}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        headers.append(base if count == 1 else f"{base}_{count}")
    return headers


def _field_slug(label: str) -> str:
    key = canonical_label(label)
    mapping = {
        "start time": "start_time",
        "end time": "end_time",
        "type of pipe": "type_of_pipe",
        "casing type": "casing_type",
        "outside diameter in": "outside_diameter_in",
        "inside diameter in": "inside_diameter_in",
        "inside diameter i n": "inside_diameter_in",
        "inside diameter": "inside_diameter_in",
        "weight lbm ft": "weight_lbm_ft",
        "grade": "grade",
        "connection": "connection",
        "length m": "length_m",
        "top mmd": "top_mmd",
        "bottom mmd": "bottom_mmd",
        "description": "description",
        "comment": "comment",
    }
    if key in mapping:
        return mapping[key]
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug or "unknown_field"


def _parse_casing_liner_tubing(rows: list[list[str]]) -> list[dict]:
    cleaned_rows = [[_normalize_cell(cell) for cell in row] for row in rows]
    cleaned_rows = [row for row in cleaned_rows if any(row)]
    if not cleaned_rows:
        return []

    width = max(len(row) for row in cleaned_rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in cleaned_rows]
    fields: dict[str, list[str]] = {}
    for row in normalized_rows:
        field_name = _field_slug(row[0])
        if field_name == "unknown_field":
            continue
        fields[field_name] = row[1:]

    n_entries = max((len(values) for values in fields.values()), default=0)
    records = []
    for idx in range(n_entries):
        record = {}
        for field_name, values in fields.items():
            value = values[idx] if idx < len(values) else ""
            record[field_name] = value or None
        value_fields = [name for name in record if name not in {"start_time", "end_time"}]
        if not any(record.get(name) for name in value_fields):
            continue
        records.append(record)
    return records


def _rows_to_dicts(table_title: str, rows: list[list[str]]) -> list[dict]:
    if canonical_label(table_title) == CASING_TABLE_CANONICAL:
        return _parse_casing_liner_tubing(rows)

    cleaned_rows = [[_normalize_cell(cell) for cell in row] for row in rows]
    cleaned_rows = [row for row in cleaned_rows if any(row)]
    if not cleaned_rows:
        return []
    if _row_is_title(cleaned_rows[0], table_title):
        cleaned_rows = cleaned_rows[1:]
    if len(cleaned_rows) < 2:
        return []

    width = max(len(row) for row in cleaned_rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in cleaned_rows]
    headers = _unique_headers(normalized_rows[0])

    records: list[dict] = []
    for row in normalized_rows[1:]:
        if not any(row):
            continue
        record = {headers[idx]: (value if value else None) for idx, value in enumerate(row)}
        records.append(record)
    return records


def _safe_table_filename(table_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", canonical_label(table_name)).strip("_")
    if not slug:
        slug = "unnamed_table"
    return f"{slug}.csv"


def extract_additional_pdf_tables(
    config: PipelineConfig,
    reports_df: pd.DataFrame,
    *,
    progress: bool = True,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    if reports_df.empty:
        return pd.DataFrame(columns=["report_id", "wellbore_id", "pdf_name", "tables_json"]), {}

    report_lookup = reports_df.set_index("pdf_name")[["report_id", "wellbore_id"]].to_dict("index")
    pdf_paths = sorted(config.pdf_dir.glob("*.pdf"))

    by_report: dict[int, dict[str, list[dict]]] = defaultdict(dict)
    by_table_rows: dict[str, list[dict]] = defaultdict(list)

    for idx, pdf_path in enumerate(pdf_paths, start=1):
        if progress and idx % 100 == 0:
            print(f"Extracted additional tables from {idx}/{len(pdf_paths)} PDFs...")

        lookup = report_lookup.get(pdf_path.name)
        if not lookup:
            continue
        report_id = int(lookup["report_id"])
        wellbore_id = lookup.get("wellbore_id")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    words = page.extract_words() or []
                    for table in page.find_tables():
                        table_title = _line_above_table(words, table.bbox[1])
                        if _is_useless_title(table_title):
                            continue
                        row_dicts = _rows_to_dicts(table_title, table.extract() or [])
                        if not row_dicts:
                            continue

                        existing_rows = by_report[report_id].setdefault(table_title, [])
                        existing_rows.extend(row_dicts)

                        for row_index, row in enumerate(row_dicts, start=1):
                            table_row = {
                                "report_id": report_id,
                                "wellbore_id": wellbore_id,
                                "pdf_name": pdf_path.name,
                                "page_number": page_number,
                                "row_index": row_index,
                            }
                            table_row.update(row)
                            by_table_rows[table_title].append(table_row)
        except Exception:
            continue

    summary_rows = []
    for _, report in reports_df[["report_id", "wellbore_id", "pdf_name"]].iterrows():
        report_id = int(report["report_id"])
        report_tables = by_report.get(report_id, {})
        summary_rows.append(
            {
                "report_id": report_id,
                "wellbore_id": report["wellbore_id"],
                "pdf_name": report["pdf_name"],
                "tables_json": json.dumps(report_tables, ensure_ascii=False),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    tables = {
        table_name: pd.DataFrame(rows)
        for table_name, rows in sorted(by_table_rows.items(), key=lambda item: canonical_label(item[0]))
        if rows
    }
    return summary_df, tables


def save_outputs_addition(
    config: PipelineConfig,
    *,
    reports_df: pd.DataFrame,
    sections_df: pd.DataFrame,
    operations_df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    fluid_df: pd.DataFrame,
    keywords_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    progress: bool = True,
) -> Path:
    output_dir = config.root / "outputs_addition"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs_csv_names = {path.name for path in config.output_dir.glob("*.csv")}
    for name in outputs_csv_names:
        duplicate_path = output_dir / name
        if duplicate_path.exists():
            duplicate_path.unlink()

    by_report_df, additional_tables = extract_additional_pdf_tables(config, reports_df, progress=progress)
    by_report_df.to_csv(output_dir / "pdf_additional_tables_by_report.csv", index=False)

    manifest_rows = []
    for table_name, table_df in additional_tables.items():
        filename = _safe_table_filename(table_name)
        table_df.to_csv(output_dir / filename, index=False)
        manifest_rows.append({"table_name": table_name, "file_name": filename, "rows": int(len(table_df))})

    pd.DataFrame(manifest_rows).to_csv(output_dir / "pdf_additional_tables_manifest.csv", index=False)
    return output_dir
