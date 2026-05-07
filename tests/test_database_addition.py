from pathlib import Path
import sqlite3

import pandas as pd

from eilink_pipeline.database import addition_table_name_from_csv, inspect_database, save_outputs_addition_tables_to_database


def test_addition_table_name_from_csv_prefixes_and_sanitizes():
    assert addition_table_name_from_csv(Path("operations.csv")) == "addition_operations"
    assert addition_table_name_from_csv(Path("Gas Reading Information.csv")) == "addition_gas_reading_information"


def test_save_outputs_addition_tables_to_database(tmp_path: Path):
    db_path = tmp_path / "test.db"
    out_dir = tmp_path / "outputs_addition"
    out_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        pd.DataFrame([{"operation_id": 1, "remark": "core table should not be touched"}]).to_sql(
            "operations",
            conn,
            if_exists="replace",
            index=False,
        )

    pd.DataFrame([{"operation_id": 99, "remark": "addition row"}]).to_csv(out_dir / "operations.csv", index=False)
    pd.DataFrame([{"report_id": 1, "value": "x"}]).to_csv(out_dir / "pore_pressure.csv", index=False)

    save_outputs_addition_tables_to_database(db_path, out_dir)

    tables = inspect_database(db_path)["table_name"].tolist()
    assert "operations" in tables
    assert "addition_operations" in tables
    assert "addition_pore_pressure" in tables
