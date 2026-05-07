# eiLink RA DS 2026 - PDF Extraction, NLP, and NDS Matching

Production-ready pipeline for the Stage 1 task:

1. Parse drilling daily report PDFs from `PDF_version_1000/`.
2. Extract structured metadata, sections, operations, equipment failures, and drilling fluid rows.
3. Store cleaned data in SQLite.
4. Match NDS events from `nds_events.xlsx` to operation excerpts.
5. Generate NLP outputs, benchmark scores, CSV exports, and a quality report.

## Setup

Install dependencies with UV:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

## Run The Pipeline

Regenerate `ei_reports.db`, all files under `outputs/`, and additional extracted table files under `outputs_addition/`:

```bash
uv run eilink-pipeline run
```

Inspect database row counts:

```bash
uv run eilink-pipeline inspect-db
```

Regenerate only the Markdown quality report from saved outputs:

```bash
uv run eilink-pipeline quality
```

## Outputs

- `ei_reports.db`: SQLite database with production tables.
- `outputs/reports_metadata.csv`
- `outputs/report_sections.csv`
- `outputs/operations.csv`
- `outputs/equipment_failures.csv`
- `outputs/drilling_fluid.csv`
- `outputs/tfidf_keywords_per_report.csv`
- `outputs/nds_event_matching_results.csv`
- `outputs/matching_benchmark.csv`
- `outputs/parse_quality_checks.csv`
- `outputs/quality_report.md`
- `outputs/run_summary.json`
- `outputs_addition/pdf_additional_tables_by_report.csv`
- `outputs_addition/pdf_additional_tables_manifest.csv`
- `outputs_addition/*.csv` for additional PDF table families (for example `pore_pressure.csv`, `survey_station.csv`, `lithology_information.csv`)

## Database Tables

- `reports`
- `report_sections`
- `operations`
- `equipment_failures`
- `drilling_fluid`
- `report_keywords`
- `nds_event_matches`
- `parse_quality_checks`
- `addition_*` tables loaded from `outputs_addition/*.csv` (for example `addition_pore_pressure`, `addition_survey_station`)

## Quality Improvements

- Metadata extraction stops at the next known label instead of stealing unrelated later values.
- Date, numeric, and flag fields are type-normalized.
- Section headers are rejected from numeric metadata fields.
- `-999.99` and related sentinel values are stored as `NULL`.
- Mostly empty drilling fluid rows are dropped; partial rows are retained with parse warnings.
- NDS matching benchmarks word TF-IDF, char TF-IDF, RapidFuzz, BM25, keyword overlap, and ensemble scoring.
