from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

TABLE_ORDER = [
    "reports",
    "report_sections",
    "operations",
    "equipment_failures",
    "drilling_fluid",
    "report_keywords",
    "nds_event_matches",
    "parse_quality_checks",
]


def _sanitize_table_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
    return sanitized or "table"


def addition_table_name_from_csv(csv_path: Path) -> str:
    return f"addition_{_sanitize_table_name(csv_path.stem)}"


def save_database(
    db_path: Path,
    *,
    reports_df: pd.DataFrame,
    sections_df: pd.DataFrame,
    operations_df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    fluid_df: pd.DataFrame,
    keywords_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    quality_df: pd.DataFrame,
) -> None:
    with sqlite3.connect(db_path) as conn:
        reports_df.to_sql("reports", conn, if_exists="replace", index=False)
        sections_df.to_sql("report_sections", conn, if_exists="replace", index=False)
        operations_df.to_sql("operations", conn, if_exists="replace", index=False)
        equipment_df.to_sql("equipment_failures", conn, if_exists="replace", index=False)
        fluid_df.to_sql("drilling_fluid", conn, if_exists="replace", index=False)
        keywords_df.to_sql("report_keywords", conn, if_exists="replace", index=False)
        matches_df.to_sql("nds_event_matches", conn, if_exists="replace", index=False)
        quality_df.to_sql("parse_quality_checks", conn, if_exists="replace", index=False)


def save_outputs_addition_tables_to_database(db_path: Path, outputs_addition_dir: Path) -> None:
    csv_files = sorted(outputs_addition_dir.glob("*.csv"))
    if not csv_files:
        return

    with sqlite3.connect(db_path) as conn:
        for csv_path in csv_files:
            df = pd.read_csv(csv_path)
            table_name = addition_table_name_from_csv(csv_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)


def inspect_database(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        table_names = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            conn,
        )["name"].tolist()
        rows = []
        for table_name in table_names:
            count = pd.read_sql_query(f'SELECT COUNT(*) AS row_count FROM "{table_name}"', conn)["row_count"].iloc[0]
            rows.append({"table_name": table_name, "row_count": int(count)})
    return pd.DataFrame(rows)
