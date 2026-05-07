from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from eilink_pipeline.additional_tables import save_outputs_addition
from eilink_pipeline.analysis import keyword_extraction_per_report
from eilink_pipeline.config import DEFAULT_CONFIG, PipelineConfig
from eilink_pipeline.database import inspect_database, save_database, save_outputs_addition_tables_to_database
from eilink_pipeline.extraction import build_corpus
from eilink_pipeline.matching import match_nds_events
from eilink_pipeline.quality import build_quality_rows, read_table_counts, write_quality_report


def ensure_output_dir(config: PipelineConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)


def save_outputs(
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
    run_summary: dict,
) -> None:
    reports_df.to_csv(config.output_dir / "reports_metadata.csv", index=False)
    sections_df.to_csv(config.output_dir / "report_sections.csv", index=False)
    operations_df.to_csv(config.output_dir / "operations.csv", index=False)
    equipment_df.to_csv(config.output_dir / "equipment_failures.csv", index=False)
    fluid_df.to_csv(config.output_dir / "drilling_fluid.csv", index=False)
    keywords_df.to_csv(config.output_dir / "tfidf_keywords_per_report.csv", index=False)
    matches_df.to_csv(config.output_dir / "nds_event_matching_results.csv", index=False)
    quality_df.to_csv(config.output_dir / "parse_quality_checks.csv", index=False)

    benchmark_cols = [
        "event_id",
        "well",
        "matched_pdf",
        "score_tfidf_word",
        "score_tfidf_char",
        "score_fuzzy",
        "score_bm25",
        "score_keyword_overlap",
        "ensemble_score",
        "matched_operation_id",
    ]
    matches_df[[col for col in benchmark_cols if col in matches_df.columns]].to_csv(config.output_dir / "matching_benchmark.csv", index=False)
    (config.output_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")


def run_pipeline(config: PipelineConfig = DEFAULT_CONFIG, *, progress: bool = True) -> dict:
    ensure_output_dir(config)
    print("Building corpus from PDFs...")
    reports_df, sections_df, operations_df, equipment_df, fluid_df, parser_quality_df = build_corpus(config, progress=progress)

    print("Running TF-IDF keyword extraction...")
    keywords_df = keyword_extraction_per_report(reports_df, top_n=12)

    print("Running NDS event matching...")
    nds_df = pd.read_excel(config.nds_path)
    matches_df = match_nds_events(nds_df, reports_df, operations_df)

    quality_df = build_quality_rows(
        reports_df=reports_df,
        operations_df=operations_df,
        equipment_df=equipment_df,
        fluid_df=fluid_df,
        matches_df=matches_df,
        existing_quality_df=parser_quality_df,
    )

    run_summary = {
        "reports_total": int(len(reports_df)),
        "operations_total": int(len(operations_df)),
        "equipment_failures_total": int(len(equipment_df)),
        "drilling_fluid_rows_total": int(len(fluid_df)),
        "keywords_rows_total": int(len(keywords_df)),
        "nds_events_total": int(len(nds_df)),
        "nds_events_matched": int(matches_df["matched"].sum()) if not matches_df.empty else 0,
        "quality_checks_total": int(len(quality_df)),
        "db_path": str(config.db_path),
    }

    print("Saving database and output files...")
    save_database(
        config.db_path,
        reports_df=reports_df,
        sections_df=sections_df,
        operations_df=operations_df,
        equipment_df=equipment_df,
        fluid_df=fluid_df,
        keywords_df=keywords_df,
        matches_df=matches_df,
        quality_df=quality_df,
    )
    save_outputs(
        config,
        reports_df=reports_df,
        sections_df=sections_df,
        operations_df=operations_df,
        equipment_df=equipment_df,
        fluid_df=fluid_df,
        keywords_df=keywords_df,
        matches_df=matches_df,
        quality_df=quality_df,
        run_summary=run_summary,
    )
    save_outputs_addition(
        config,
        reports_df=reports_df,
        sections_df=sections_df,
        operations_df=operations_df,
        equipment_df=equipment_df,
        fluid_df=fluid_df,
        keywords_df=keywords_df,
        matches_df=matches_df,
        quality_df=quality_df,
        progress=progress,
    )
    save_outputs_addition_tables_to_database(config.db_path, config.root / "outputs_addition")

    table_counts = read_table_counts(config.db_path)
    write_quality_report(
        config.output_dir / "quality_report.md",
        run_summary=run_summary,
        table_counts=table_counts,
        quality_df=quality_df,
        matches_df=matches_df,
    )
    print(json.dumps(run_summary, indent=2))
    return run_summary


def generate_quality_report(config: PipelineConfig = DEFAULT_CONFIG) -> Path:
    table_counts = read_table_counts(config.db_path)
    with pd.option_context("mode.copy_on_write", True):
        try:
            quality_df = pd.read_csv(config.output_dir / "parse_quality_checks.csv")
        except FileNotFoundError:
            quality_df = pd.DataFrame()
        try:
            matches_df = pd.read_csv(config.output_dir / "nds_event_matching_results.csv")
        except FileNotFoundError:
            matches_df = pd.DataFrame()
        try:
            run_summary = json.loads((config.output_dir / "run_summary.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            run_summary = {"db_path": str(config.db_path)}
    output_path = config.output_dir / "quality_report.md"
    write_quality_report(output_path, run_summary=run_summary, table_counts=table_counts, quality_df=quality_df, matches_df=matches_df)
    return output_path


def inspect_db(config: PipelineConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    return inspect_database(config.db_path)


def config_from_root(root: Path | str | None) -> PipelineConfig:
    return PipelineConfig.from_root(root) if root else DEFAULT_CONFIG
