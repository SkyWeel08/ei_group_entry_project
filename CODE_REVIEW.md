# Code Review - eiLink RA DS 2026 Pipeline (Detailed Logic Review)

> **Project:** `eilink-pipeline v0.1.0`
> **Review date:** 2026-05-06
> **Repository root:** `C:\Users\wlf01\Downloads\RA DS - 2026\Task_DS\ei_group_entry_project`

---

## Table of Contents

1. [Executive Findings (Prioritized)](#1-executive-findings-prioritized)
2. [What Was Implemented in This Task](#2-what-was-implemented-in-this-task)
3. [Architecture and End-to-End Data Flow](#3-architecture-and-end-to-end-data-flow)
4. [Core Pipeline Orchestration (`pipeline.py`)](#4-core-pipeline-orchestration-pipelinepy)
5. [PDF Ingestion and Corpus Build (`extraction.py`)](#5-pdf-ingestion-and-corpus-build-extractionpy)
6. [Parsing Logic Deep Dive (`parsers.py`)](#6-parsing-logic-deep-dive-parserspy)
7. [Text Normalization and Guardrails (`text_utils.py`)](#7-text-normalization-and-guardrails-text_utilspy)
8. [NLP Layer (`nlp.py`)](#8-nlp-layer-nlppy)
9. [NDS Event Matching Methodology (`matching.py`)](#9-nds-event-matching-methodology-matchingpy)
10. [Keyword Extraction (`analysis.py`)](#10-keyword-extraction-analysispy)
11. [Quality Framework (`quality.py`)](#11-quality-framework-qualitypy)
12. [Database Persistence (`database.py`)](#12-database-persistence-databasepy)
13. [Additional PDF Tables Extraction (`additional_tables.py`)](#13-additional-pdf-tables-extraction-additional_tablespy)
14. [CLI and Config (`cli.py`, `config.py`)](#14-cli-and-config-clipy-configpy)
15. [Outputs and What They Mean](#15-outputs-and-what-they-mean)
16. [Testing Coverage Analysis](#16-testing-coverage-analysis)
17. [Recommendations (Implementation-Ready)](#17-recommendations-implementation-ready)

---

## 1. Executive Findings (Prioritized)

### High

1. **Match decision is too permissive: any in-well best candidate becomes `matched=True` even for low scores.**
   - **Where:** `eilink_pipeline/matching.py` (`candidates.empty` branch vs best-candidate branch).
   - **Impact:** Can inflate `nds_events_matched` and confidence in final analytics.
   - **Evidence:** In `outputs/nds_event_matching_results.csv`, one matched event has low `ensemble_score` (~0.1485).

### Medium

2. **Additional-table extraction hides failures silently.**
   - **Where:** `eilink_pipeline/additional_tables.py` uses `except Exception: continue`.
   - **Impact:** Missing extracted rows may look like real zero rows instead of parser failures.

### Low

3. **Minor dead fallback path in metadata period split.**
   - **Where:** `parse_metadata` references `period_raw_raw`, which is never populated.

4. **Lint hygiene issue in tests.**
   - **Where:** `tests/test_database_addition.py` import ordering (`ruff I001`).

---

## 2. What Was Implemented in This Task

From commit history:

- **Base production pipeline refactor** from notebook/script style into package modules:
  - parser + normalization layer,
  - NLP enrichment,
  - NDS matching benchmark logic,
  - DB persistence,
  - CSV + Markdown reporting.
- **Additional tables extension**:
  - PDF table extraction beyond core task tables,
  - `outputs_addition/*.csv`,
  - loading these CSVs into SQLite as `addition_*` tables.
- **Test suite** expanded to cover parser behavior, matching behavior, and additional-table conversion/load semantics.

Current output scale confirms full run executed:

- 1000 reports parsed
- 10,597 operations
- 2,830 drilling fluid rows
- 5,952 quality checks

---

## 3. Architecture and End-to-End Data Flow

### Input artifacts

- `PDF_version_1000/*.pdf` (source unstructured reports)
- `nds_events.xlsx` (target events to match)

### Core flow

1. `build_corpus` parses all PDFs into structured frames.
2. `keyword_extraction_per_report` adds TF-IDF keywords.
3. `match_nds_events` links NDS events to operation rows.
4. `build_quality_rows` merges parser checks + consistency checks + matching warnings.
5. `save_database` writes core tables.
6. `save_outputs` writes main CSV outputs.
7. `save_outputs_addition` extracts extra tables into `outputs_addition`.
8. `save_outputs_addition_tables_to_database` writes `addition_*` tables.
9. `write_quality_report` compiles markdown summary.

### Design pattern observed

- **Batch ETL pipeline with deterministic transforms**, no model training, no stochastic behavior except scoring tie/argmax behavior in matching.
- **DataFrames as module boundaries**: each stage receives/returns frames, making inter-stage contracts explicit.

---

## 4. Core Pipeline Orchestration (`pipeline.py`)

### `run_pipeline(config, progress=True)`

This is the main orchestration method. Logic by stage:

1. **Preparation**
   - `ensure_output_dir` creates output folder.
2. **Parsing stage**
   - `build_corpus` returns:
     - `reports_df`,
     - `sections_df`,
     - `operations_df`,
     - `equipment_df`,
     - `fluid_df`,
     - `parser_quality_df`.
3. **NLP analytics stage**
   - `keyword_extraction_per_report(reports_df, top_n=12)`.
4. **Matching stage**
   - `pd.read_excel(config.nds_path)` then `match_nds_events(...)`.
5. **Quality aggregation stage**
   - `build_quality_rows(..., existing_quality_df=parser_quality_df)`.
6. **Run summary materialization**
   - Counts rows from each output frame.
7. **Persistence stage**
   - `save_database(...)` for core tables.
   - `save_outputs(...)` for CSV snapshots.
   - `save_outputs_addition(...)` for extra table families.
   - `save_outputs_addition_tables_to_database(...)` for `addition_*` tables.
8. **Report stage**
   - Reads DB counts and writes `quality_report.md`.

### Why this structure works

- Keeps critical-path logic linear and auditable.
- Quality checks are produced in same run as data, preventing stale QA status.
- Output CSVs and DB are synchronized from the same in-memory frames.

---

## 5. PDF Ingestion and Corpus Build (`extraction.py`)

### `extract_pdf_text(pdf_path)`

Two-step extraction strategy:

1. Try `pypdf` text extraction first (fast, simple).
2. If empty/failed, fallback to `pdfplumber` (more robust for some layouts).

Both results are passed through `clean_text` for newline/whitespace normalization.

### `parse_single_pdf(pdf_path, config)`

Workflow:

1. Extract full text.
2. Parse metadata and metadata checks (`parse_metadata`).
3. Parse canonical sections (`parse_sections`).
4. Attach section raw text into report columns (`build_report_sections_columns`).
5. Parse operations/equipment/drilling fluid from section slices.
6. Return `ParsedReport` dataclass.

### `build_corpus(config, pdf_files=None, progress=True)`

This function is the key ETL collector:

- Iterates over PDFs.
- Wraps `parse_single_pdf` in try/except.
- On failure, emits minimal report with `parse_error` and quality check `pdf_parse_failed` instead of crashing entire batch.
- Assigns synthetic integer IDs (`report_id`, `section_id`, `operation_id`, ...).

**Method used:** fail-soft parsing at document granularity.

---

## 6. Parsing Logic Deep Dive (`parsers.py`)

## 6.1 Metadata parsing strategy

### Metadata schema

`METADATA_FIELDS` defines field-by-field extraction contracts:

- accepted labels (`labels` tuple),
- expected type (`text`, `number`, `int`, `datetime`, `flag`).

### `extract_labeled_value(lines, labels, max_lookahead=4)`

This function is the main anti-misalignment logic.

How it works:

1. Find line that matches target label (canonicalized) or inline `label: value` case.
2. If inline value exists, return it immediately.
3. Else inspect next lines up to lookahead.
4. Stop if next token is:
   - another known label,
   - section header,
   - line ending with colon.
5. Return first acceptable candidate value.

This prevents "value stealing" across labels.

### `normalize_metadata_value`

Dispatches to strict normalizers based on declared type.

- numbers -> `normalize_number`
- ints -> `normalize_integer`
- datetime -> `normalize_datetime`
- flags -> `normalize_flag`
- text -> `normalize_text_value`

### `parse_metadata(text)`

For each field:

- extract raw value,
- normalize it,
- store both clean and raw versions,
- emit quality warnings when raw exists but normalized value rejected,
- emit info checks for "no accepted value" when label exists but value is not valid.

Then derives period boundaries using `split_period(...)`.

**Result:** one report dict + list of quality checks.

## 6.2 Section slicing strategy

### `parse_sections(text)`

Uses `extract_section(start_markers, end_markers)` for five named sections:

- summary activities,
- summary planned,
- operations,
- equipment failure,
- drilling fluid.

Each section row includes:

- `section_name`,
- cleaned section text,
- char count,
- presence flag.

## 6.3 Operations parsing strategy

### Dual parser approach

`parse_operations(section_text)` tries:

1. `parse_operations_from_row_lines` (preferred structured pattern)
2. fallback `parse_operations_from_token_lines` (looser token stream parsing)

#### A) Row-line parser

- Detects rows with regex:
  - `start_time end_time depth activity...`
- Splits activity/state/remark via `_split_activity_state_remark`.
- Buffers multi-line remarks until next row start.
- Flushes buffer into `_operation_row`.

#### B) Token-line parser

- Detects row starts by token triplet:
  - time, time, number.
- Consumes activity tokens until state marker or next row start.
- Consumes remark tokens until next row start.

### `_operation_row(...)`

Builds normalized operation record and enriches with:

- `activity_label` from rule-based classifier,
- NER-derived JSON fields (`depths`, `equipment`, `measurements`, `time_refs`).

## 6.4 Equipment failures parsing

`parse_equipment_failures(section_text)` uses token scanning with row start rule:

- first token time,
- second token numeric depth.

Then extracts:

- `system_class` (text span),
- downtime numeric,
- optional repaired time,
- remark span.

Row retained only when essential fields exist (`system_class` + `remark`).

## 6.5 Drilling fluid parsing

This parser uses vertical segment extraction by labels:

1. For each expected label column, collect values under that label until next label.
2. Align by row index across columns.
3. Normalize each field by type.
4. Drop fully empty rows.
5. Keep partially populated rows but emit warning `partial_fluid_row`.

Important cleanup behavior:

- sentinel values like `-999.99` become `None` via numeric normalizer.

---

## 7. Text Normalization and Guardrails (`text_utils.py`)

This module defines global parsing safety rules.

### Key methods

- `canonical_label`: lowercases, removes punctuation/noise, normalizes special chars.
- `is_section_header`: blocks section titles from being treated as data.
- `normalize_number`: extracts first numeric token, converts comma decimal, rejects sentinels.
- `normalize_datetime`: accepts strict `YYYY-MM-DD` with optional `HH:MM`.
- `split_period`: extracts exactly `start - end` datetime range.

### Why this matters

Without this guardrail layer, metadata fields frequently absorb table/section text from PDFs.

---

## 8. NLP Layer (`nlp.py`)

Methodology is deterministic and explainable:

### `extract_entities(text)`

Regex + dictionary extraction for:

- depth mentions (`mmd`, `mtvd`, `md`, `tvd`, `m`),
- time refs (`HH:MM`),
- measurements (rpm, bar, lpm, tons, knm, m3),
- equipment dictionary hits.

Returns deduplicated lists via `unique(...)`.

### `classify_activity(text)`

Keyword-rule classifier using `ACTIVITY_RULES`.

Examples:

- "ream / drilled / mill" -> `CUT`
- "pooh / pull out" -> `TRIP_OUT`
- "failure / leak" -> `EQUIPMENT_FAILURE`

No ML model; behavior is fully transparent and testable.

---

## 9. NDS Event Matching Methodology (`matching.py`)

### Candidate generation

1. Join operations with report metadata (`pdf_name`, `wellbore_id`).
2. Normalize well names with `normalize_well_name`.
3. For each NDS event, keep operations from same normalized well only.

### Feature scoring (`score_candidates`)

For event text vs each candidate operation text:

1. **Word TF-IDF cosine** (`ngram_range=(1,2)`) -> semantic lexical overlap.
2. **Char TF-IDF cosine** (`analyzer=char_wb`, 3-5 grams) -> robust to typos/variants.
3. **RapidFuzz token-set ratio** -> fuzzy token similarity.
4. **BM25 score** over tokenized corpus -> IR relevance.
5. **Keyword overlap Jaccard** -> explicit set overlap ratio.

BM25 is min-max normalized before blending.

### Ensemble formula

```text
ensemble =
  0.35 * tfidf_word
+ 0.25 * tfidf_char
+ 0.20 * fuzzy
+ 0.10 * bm25
+ 0.10 * keyword_overlap
```

### Selection

- `best_idx = argmax(ensemble_score)`.
- top N candidates serialized into `top_candidates_json` for traceability.

### Current decision rule weakness

- If candidates exist, result is always `matched=True` regardless of absolute score.
- No threshold gate (e.g., `ensemble >= 0.30`) and no margin check vs second-best candidate.

---

## 10. Keyword Extraction (`analysis.py`)

`keyword_extraction_per_report` builds a composite text per report from:

- summary activities,
- summary planned,
- operations section raw,
- equipment failure section raw.

Then applies corpus-level TF-IDF and stores top N terms per report.

Method details:

- stopwords: english
- max_features: 12000
- token pattern requiring alpha-start tokens
- unigrams + bigrams

Result columns:

- `report_id`, `pdf_name`, `keyword_rank`, `keyword`, `tfidf_score`

---

## 11. Quality Framework (`quality.py`)

## 11.1 `build_quality_rows(...)`

Aggregates quality issues from multiple sources:

1. Existing parser checks (metadata/fluid parse issues).
2. Numeric contamination checks: section marker text in numeric report fields.
3. Sentinel residue checks across tables.
4. Unmatched NDS events -> warning rows.

It then assigns/reassigns sequential `quality_check_id`.

## 11.2 `write_quality_report(...)`

Builds markdown report with:

- run summary JSON block,
- table row counts,
- quality check severity stats,
- top quality-check rows,
- per-event NDS matching table.

This is an explainability artifact for non-technical review.

---

## 12. Database Persistence (`database.py`)

### Core save

`save_database(...)` writes core frames with `if_exists='replace'`.

Implications:

- deterministic full refresh,
- no incremental append semantics,
- simple reproducibility.

### Additional tables save

`save_outputs_addition_tables_to_database(...)`:

1. scans `outputs_addition/*.csv`,
2. sanitizes table names,
3. writes each to SQLite as `addition_<slug>`.

Namespace isolation avoids collisions with core tables.

---

## 13. Additional PDF Tables Extraction (`additional_tables.py`)

This module is an independent extraction subsystem.

### Table title detection

- For each table bbox, reads line directly above table (`_line_above_table`).
- Normalizes title and filters noise (`_is_useless_title`).

### Row normalization

- `_normalize_cell` trims whitespace/newlines and repairs doubled characters (`_dedupe_doubled_token`).
- `_unique_headers` avoids duplicate column names by suffixing `_2`, `_3`, ...

### Special-case transform: `Casing Liner Tubing`

- Recognized as transposed format.
- `_parse_casing_liner_tubing` pivots row-wise field labels into per-entry records.
- Produces clean per-row schema (`start_time`, `type_of_pipe`, `inside_diameter_in`, ...).

### Aggregation outputs

- `pdf_additional_tables_by_report.csv`: JSON map of table_name -> rows per report.
- `pdf_additional_tables_manifest.csv`: table family manifest with row counts.
- individual CSV per detected table family.

### Main quality gap

Extraction exceptions are swallowed silently; recommend logging them into quality checks.

---

## 14. CLI and Config (`cli.py`, `config.py`)

### Config model

`PipelineConfig` maps root to:

- `pdf_dir`,
- `nds_path`,
- `db_path`,
- `output_dir`.

This keeps environment setup predictable.

### CLI commands

- `eilink-pipeline run` -> full pipeline.
- `eilink-pipeline quality` -> regenerate markdown from saved outputs.
- `eilink-pipeline inspect-db` -> DB table row counts.

Typer + Rich combination is appropriate for reproducible command-line workflows.

---

## 15. Outputs and What They Mean

From current run artifacts:

- `outputs/run_summary.json`
  - 1000 reports parsed.
  - 3 of 4 NDS events marked matched.
- `outputs/parse_quality_checks.csv`
  - 5952 checks total.
  - mostly `info`/`warning`, no hard-stop error policy.
- `outputs/quality_report.md`
  - clear QA narrative with tables and NDS match table.
- `outputs_addition/pdf_additional_tables_manifest.csv`
  - 11 additional table families extracted.

SQLite table inventory includes:

- 8 core tables from `TABLE_ORDER`,
- additional `addition_*` tables,
- totaling 21 tables.

---

## 16. Testing Coverage Analysis

Executed:

```bash
.\.venv\Scripts\python.exe -m pytest
```

Result: **13 passed**.

### What is well covered

- Metadata stop-at-next-label behavior.
- Operations parsing + activity/entity enrichment basics.
- Drilling fluid sentinel handling.
- Matching behavior for matched and unmatched wells.
- Additional-table conversion helpers, including transposed casing format.
- DB write of additional tables without clobbering core table names.

### Gaps worth adding

1. Matching threshold tests (accepted/rejected by score boundary).
2. Additional-table extraction failure observability test.
3. End-to-end test that validates `addition_*` tables appear after full `run` command.
4. Regression tests for ambiguous metadata labels across multiline blocks.

---

## 17. Recommendations (Implementation-Ready)

1. **Introduce matching threshold and confidence flag.**
   - Add config: `match_min_score` (e.g., 0.25 or tuned by validation set).
   - Rule:
     - if `best_score < threshold` -> `matched=False`, reason `low_confidence`.
2. **Log additional-table extraction failures.**
   - Replace silent `except` with error capture rows containing `pdf_name`, `page_number`, `exception`.
   - Feed into `quality_df` and quality report.
3. **Fix small parser fallback typo.**
   - Replace `period_raw_raw` fallback with explicit intended source or remove dead branch.
4. **Add optional strict mode for pipeline quality gating.**
   - Fail run when critical checks exceed threshold (for production CI).
5. **Clean lint warning** in test imports.

---

## Final Technical Assessment

The implementation is strong and production-oriented for a parsing-heavy analytics task: modularized ETL, practical normalization, explainable matching features, quality artifacts, and working tests. The primary improvement needed for analytical trust is **match confidence calibration** and **better observability of additional-table extraction failures**. Once those are addressed, this pipeline will be significantly more defensible for downstream reporting and decision-making.
