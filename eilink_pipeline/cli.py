from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from eilink_pipeline.pipeline import config_from_root, generate_quality_report, inspect_db, run_pipeline

app = typer.Typer(help="eiLink PDF extraction, NLP, and NDS matching pipeline.")
console = Console()


@app.command()
def run(
    root: Path | None = typer.Option(None, help="Project root containing PDF_version_1000 and nds_events.xlsx."),
    quiet: bool = typer.Option(False, help="Disable progress output."),
) -> None:
    """Regenerate the SQLite database and all output files."""
    config = config_from_root(root)
    run_pipeline(config, progress=not quiet)


@app.command()
def quality(root: Path | None = typer.Option(None, help="Project root containing outputs and ei_reports.db.")) -> None:
    """Regenerate the Markdown quality report from saved outputs."""
    config = config_from_root(root)
    output_path = generate_quality_report(config)
    console.print(f"Quality report written to {output_path}")


@app.command("inspect-db")
def inspect_db_command(root: Path | None = typer.Option(None, help="Project root containing ei_reports.db.")) -> None:
    """Print row counts for database tables."""
    config = config_from_root(root)
    df = inspect_db(config)
    table = Table(title=str(config.db_path))
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    for _, row in df.iterrows():
        table.add_row(str(row["table_name"]), str(row["row_count"]))
    console.print(table)
