from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber
from pypdf import PdfReader

from eilink_pipeline.config import PipelineConfig
from eilink_pipeline.models import ParsedReport
from eilink_pipeline.parsers import (
    build_report_sections_columns,
    parse_drilling_fluid,
    parse_equipment_failures,
    parse_metadata,
    parse_operations,
    parse_sections,
)
from eilink_pipeline.text_utils import clean_text


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if text.strip():
            return clean_text(text)
    except Exception:
        pass

    with pdfplumber.open(pdf_path) as pdf:
        return clean_text("\n".join(page.extract_text() or "" for page in pdf.pages))


def parse_single_pdf(pdf_path: Path, config: PipelineConfig) -> ParsedReport:
    text = extract_pdf_text(pdf_path)
    report, metadata_checks = parse_metadata(text)
    sections, raw_sections = parse_sections(text)
    build_report_sections_columns(report, raw_sections)

    report["pdf_name"] = pdf_path.name
    report["pdf_path"] = str(pdf_path.relative_to(config.root))
    report["full_text"] = text
    report["parse_error"] = None

    operations = parse_operations(raw_sections.get("operations", ""))
    equipment_failures = parse_equipment_failures(raw_sections.get("equipment_failure", ""))
    drilling_fluid_rows, fluid_checks = parse_drilling_fluid(raw_sections.get("drilling_fluid", ""))

    return ParsedReport(
        report=report,
        sections=sections,
        operations=operations,
        equipment_failures=equipment_failures,
        drilling_fluid_rows=drilling_fluid_rows,
        quality_checks=metadata_checks + fluid_checks,
    )


def _frame(rows: list[dict], id_name: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if id_name and not df.empty:
        df.insert(0, id_name, np.arange(1, len(df) + 1))
    return df


def build_corpus(
    config: PipelineConfig,
    *,
    pdf_files: list[Path] | None = None,
    progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = pdf_files or sorted(config.pdf_dir.glob("*.pdf"))
    reports: list[dict] = []
    sections: list[dict] = []
    operations: list[dict] = []
    equipment_failures: list[dict] = []
    drilling_fluid_rows: list[dict] = []
    quality_checks: list[dict] = []

    for idx, pdf_path in enumerate(paths, start=1):
        if progress and idx % 100 == 0:
            print(f"Parsed {idx}/{len(paths)} PDFs...")
        try:
            parsed = parse_single_pdf(pdf_path, config)
        except Exception as exc:
            parsed = ParsedReport(
                report={
                    "pdf_name": pdf_path.name,
                    "pdf_path": str(pdf_path.relative_to(config.root)),
                    "full_text": "",
                    "parse_error": str(exc),
                },
                sections=[],
                operations=[],
                equipment_failures=[],
                drilling_fluid_rows=[],
                quality_checks=[
                    {
                        "table_name": "reports",
                        "field_name": "parse_error",
                        "severity": "error",
                        "check_name": "pdf_parse_failed",
                        "message": str(exc),
                    }
                ],
            )

        reports.append(parsed.report)
        report_id = len(reports)

        for row in parsed.sections:
            row["report_id"] = report_id
            sections.append(row)
        for row in parsed.operations:
            row["report_id"] = report_id
            operations.append(row)
        for row in parsed.equipment_failures:
            row["report_id"] = report_id
            equipment_failures.append(row)
        for row in parsed.drilling_fluid_rows:
            row["report_id"] = report_id
            drilling_fluid_rows.append(row)
        for row in parsed.quality_checks:
            row["report_id"] = report_id
            quality_checks.append(row)

    reports_df = _frame(reports, "report_id")
    sections_df = _frame(sections, "section_id")
    operations_df = _frame(operations, "operation_id")
    equipment_df = _frame(equipment_failures, "equipment_failure_id")
    fluid_df = _frame(drilling_fluid_rows, "fluid_row_id")
    quality_df = _frame(quality_checks, "quality_check_id")
    return reports_df, sections_df, operations_df, equipment_df, fluid_df, quality_df
