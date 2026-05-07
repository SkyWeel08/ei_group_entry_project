from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from eilink_pipeline.database import TABLE_ORDER

NUMERIC_REPORT_COLUMNS = [
    "water_depth_msl_m",
    "elevation_rkb_msl_m",
    "depth_current_mmd",
    "depth_current_mtvd",
    "depth_kickoff_mmd",
    "depth_kickoff_mtvd",
    "depth_last_casing_mmd",
    "depth_last_casing_mtvd",
    "depth_formation_strength_mmd",
    "depth_formation_strength_mtvd",
    "plug_back_depth_mmd",
    "formation_strength_g_cm3",
    "hole_diameter_in",
]


def _count_bad_marker(df: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    counts = {}
    for column in columns:
        if column in df.columns:
            series = df[column].astype(str)
            counts[column] = int(series.str.contains("Summary of activities|Summary of planned activities", case=False, regex=True).sum())
    return counts


def _count_sentinel(df: pd.DataFrame) -> int:
    count = 0
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            count += int(df[column].isin([-999.99, -999.9, -999.0]).sum())
    return count


def build_quality_rows(
    *,
    reports_df: pd.DataFrame,
    operations_df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    fluid_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    existing_quality_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = existing_quality_df.to_dict("records") if not existing_quality_df.empty else []

    for column, count in _count_bad_marker(reports_df, NUMERIC_REPORT_COLUMNS).items():
        if count:
            rows.append(
                {
                    "report_id": None,
                    "table_name": "reports",
                    "field_name": column,
                    "severity": "error",
                    "check_name": "bad_section_marker_in_numeric_field",
                    "message": f"{count} values contain a section marker",
                }
            )

    for table_name, df in [("reports", reports_df), ("operations", operations_df), ("equipment_failures", equipment_df), ("drilling_fluid", fluid_df)]:
        sentinel_count = _count_sentinel(df)
        if sentinel_count:
            rows.append(
                {
                    "report_id": None,
                    "table_name": table_name,
                    "field_name": None,
                    "severity": "error",
                    "check_name": "sentinel_number_present",
                    "message": f"{sentinel_count} sentinel values remain",
                }
            )

    if not matches_df.empty:
        unmatched = matches_df[matches_df["matched"] == False]  # noqa: E712
        for _, row in unmatched.iterrows():
            rows.append(
                {
                    "report_id": None,
                    "table_name": "nds_event_matches",
                    "field_name": "matched",
                    "severity": "warning",
                    "check_name": "nds_event_unmatched",
                    "message": f"Event {row.get('event_id')} for {row.get('well')} unmatched: {row.get('reason')}",
                }
            )

    quality_df = pd.DataFrame(rows)
    if quality_df.empty:
        quality_df = pd.DataFrame(columns=["quality_check_id", "report_id", "table_name", "field_name", "severity", "check_name", "message"])
    if "quality_check_id" not in quality_df.columns:
        quality_df.insert(0, "quality_check_id", range(1, len(quality_df) + 1))
    else:
        quality_df["quality_check_id"] = range(1, len(quality_df) + 1)
    return quality_df


def write_quality_report(
    output_path: Path,
    *,
    run_summary: dict,
    table_counts: dict[str, int],
    quality_df: pd.DataFrame,
    matches_df: pd.DataFrame,
) -> None:
    def cell(value: object) -> str:
        if pd.isna(value):
            return ""
        return str(value).replace("|", "/")

    def bool_cell(value: object) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    severity_counts = {}
    if not quality_df.empty and "severity" in quality_df.columns:
        severity_counts = quality_df["severity"].fillna("unknown").value_counts().to_dict()

    lines = [
        "# eiLink Pipeline Quality Report",
        "",
        "## Run Summary",
        "",
        "```json",
        json.dumps(run_summary, indent=2),
        "```",
        "",
        "## Table Counts",
        "",
        "| Table | Rows |",
        "| --- | ---: |",
    ]
    for table in TABLE_ORDER:
        lines.append(f"| {table} | {table_counts.get(table, 0)} |")

    lines.extend(
        [
            "",
            "## Quality Checks",
            "",
            f"- Total checks: {len(quality_df)}",
            f"- Severity counts: `{json.dumps(severity_counts, sort_keys=True)}`",
        ]
    )
    if not quality_df.empty:
        top = quality_df[["severity", "table_name", "field_name", "check_name", "message"]].head(50)
        lines.extend(["", "| Severity | Table | Field | Check | Message |", "| --- | --- | --- | --- | --- |"])
        for _, row in top.iterrows():
            lines.append(
                f"| {cell(row.get('severity'))} | {cell(row.get('table_name'))} | {cell(row.get('field_name'))} | {cell(row.get('check_name'))} | {cell(row.get('message'))} |"
            )

    lines.extend(["", "## NDS Matching", "", "| Event | Well | Matched | PDF | Ensemble | Reason |", "| ---: | --- | --- | --- | ---: | --- |"])
    if not matches_df.empty:
        for _, row in matches_df.iterrows():
            lines.append(
                f"| {cell(row.get('event_id'))} | {cell(row.get('well'))} | {bool_cell(row.get('matched'))} | {cell(row.get('matched_pdf'))} | {float(row.get('ensemble_score') or 0):.4f} | {cell(row.get('reason'))} |"
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_table_counts(db_path: Path) -> dict[str, int]:
    counts = {}
    with sqlite3.connect(db_path) as conn:
        for table in TABLE_ORDER:
            try:
                counts[table] = int(pd.read_sql_query(f'SELECT COUNT(*) AS n FROM "{table}"', conn)["n"].iloc[0])
            except Exception:
                counts[table] = 0
    return counts
