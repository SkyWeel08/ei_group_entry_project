from __future__ import annotations

import json
import re
from collections.abc import Iterable

from eilink_pipeline.models import MetadataField
from eilink_pipeline.nlp import classify_activity, extract_entities
from eilink_pipeline.text_utils import (
    canonical_label,
    compact_join,
    extract_section,
    is_missing_text,
    is_number_token,
    is_section_header,
    is_time_token,
    lines_from_text,
    normalize_datetime,
    normalize_flag,
    normalize_integer,
    normalize_number,
    normalize_text_value,
    split_period,
)

METADATA_FIELDS: dict[str, MetadataField] = {
    "wellbore_id": MetadataField(("Wellbore",)),
    "report_number": MetadataField(("Report number",), "int"),
    "period_raw": MetadataField(("Period",), "text"),
    "status": MetadataField(("Status",), "text"),
    "operator": MetadataField(("Operator",), "text"),
    "rig_name": MetadataField(("Rig Name",), "text"),
    "drilling_contractor": MetadataField(("Drilling contractor",), "text"),
    "spud_date": MetadataField(("Spud Date",), "datetime"),
    "water_depth_msl_m": MetadataField(("Water depth MSL (m)", "Water depth (m)"), "number"),
    "elevation_rkb_msl_m": MetadataField(("Elevation RKB-MSL (m)",), "number"),
    "tight_well_flag": MetadataField(("Tight well",), "flag"),
    "hpht_flag": MetadataField(("HPHT",), "flag"),
    "depth_current_mmd": MetadataField(("Depth mMD", "Depth mMd"), "number"),
    "depth_current_mtvd": MetadataField(("Depth mTVD",), "number"),
    "depth_kickoff_mmd": MetadataField(("Depth at Kick Off mMD",), "number"),
    "depth_kickoff_mtvd": MetadataField(("Depth at Kick Off mTVD",), "number"),
    "depth_last_casing_mmd": MetadataField(("Depth At Last Casing mMD",), "number"),
    "depth_last_casing_mtvd": MetadataField(("Depth At Last Casing mTVD",), "number"),
    "depth_formation_strength_mmd": MetadataField(("Depth at formation strength mMD",), "number"),
    "depth_formation_strength_mtvd": MetadataField(("Depth At Formation Strength mTVD",), "number"),
    "plug_back_depth_mmd": MetadataField(("Plug Back Depth mMD",), "number"),
    "formation_strength_g_cm3": MetadataField(("Formation strength (g/cm3)", "Formation strength (g/cm³)"), "number"),
    "hole_diameter_in": MetadataField(("Hole Dia (in)", "Hole diameter"), "number"),
    "pressure_test_type": MetadataField(("Pressure Test Type",), "text"),
}

KNOWN_LABELS = {canonical_label(label) for field in METADATA_FIELDS.values() for label in field.labels}
KNOWN_LABELS.update(
    {
        canonical_label(label)
        for label in [
            "Report creation time",
            "Days Ahead/Behind (+/-)",
            "Last BOP test",
            "Leak Off Tests",
            "Casing String",
            "Lot/Fit emw",
            "Formation",
            "Mud Lost To Formation",
        ]
    }
)


def _line_value_after_colon(line: str, labels: Iterable[str]) -> str | None:
    if ":" not in line:
        return None
    left, right = line.split(":", 1)
    if canonical_label(left) in {canonical_label(label) for label in labels}:
        return right.strip() or None
    return None


def extract_labeled_value(lines: list[str], labels: Iterable[str], max_lookahead: int = 4) -> tuple[str | None, str | None]:
    label_set = {canonical_label(label) for label in labels}
    for idx, line in enumerate(lines):
        canonical = canonical_label(line)
        matched = canonical in label_set
        inline_value = _line_value_after_colon(line, labels)
        if not matched and inline_value is None:
            continue
        if inline_value is not None:
            return inline_value, None

        for look_idx in range(idx + 1, min(idx + 1 + max_lookahead, len(lines))):
            candidate = lines[look_idx].strip()
            candidate_canonical = canonical_label(candidate)
            if not candidate:
                continue
            if candidate_canonical in label_set:
                continue
            if candidate_canonical in KNOWN_LABELS or candidate.endswith(":") or is_section_header(candidate):
                return None, "value_missing_before_next_label"
            return candidate, None
    return None, "label_not_found"


def normalize_metadata_value(raw_value: str | None, kind: str) -> object:
    if kind == "number":
        return normalize_number(raw_value)
    if kind == "int":
        return normalize_integer(raw_value)
    if kind == "datetime":
        return normalize_datetime(raw_value)
    if kind == "flag":
        return normalize_flag(raw_value)
    return normalize_text_value(raw_value)


def parse_metadata(text: str) -> tuple[dict, list[dict]]:
    lines = lines_from_text(text)
    report = {}
    checks = []
    for field_name, spec in METADATA_FIELDS.items():
        raw_value, reason = extract_labeled_value(lines, spec.labels)
        value = normalize_metadata_value(raw_value, spec.kind)
        report[field_name] = value
        report[f"{field_name}_raw"] = raw_value
        if raw_value is not None and value is None:
            checks.append(
                {
                    "table_name": "reports",
                    "field_name": field_name,
                    "severity": "warning",
                    "check_name": "metadata_value_rejected",
                    "message": f"Rejected raw value {raw_value!r} for {field_name}",
                }
            )
        elif raw_value is None and reason and reason != "label_not_found":
            checks.append(
                {
                    "table_name": "reports",
                    "field_name": field_name,
                    "severity": "info",
                    "check_name": reason,
                    "message": f"No accepted value for {field_name}",
                }
            )
    period_start, period_end = split_period(report.get("period_raw") or report.get("period_raw_raw"))
    report["period_start"] = period_start
    report["period_end"] = period_end
    return report, checks


def parse_sections(text: str) -> tuple[list[dict], dict[str, str]]:
    section_specs = {
        "summary_activities_24h": (
            ["Summary of activities (24 Hours)", "Summary of activities (24h)"],
            ["Summary of planned activities", "Operations", "Equipment Failure", "Drilling Fluid"],
        ),
        "summary_planned_24h": (
            ["Summary of planned activities (24 Hours)", "Summary of planned activities (24h)"],
            ["Operations", "Equipment Failure", "Drilling Fluid"],
        ),
        "operations": (
            ["Operations"],
            ["Equipment Failure", "Equipment Failure Information", "Drilling Fluid", "Bit Record", "Survey Station", "Pore Pressure"],
        ),
        "equipment_failure": (
            ["Equipment Failure Information", "Equipment Failure"],
            ["Drilling Fluid", "Bit Record", "Survey Station", "Pore Pressure"],
        ),
        "drilling_fluid": (
            ["Drilling Fluid"],
            ["Survey Station", "Pore Pressure", "Bit Record", "Casing Record", "BHA Record"],
        ),
    }
    sections = []
    raw_by_name = {}
    for section_name, (starts, ends) in section_specs.items():
        section_text = extract_section(text, starts, ends)
        raw_by_name[section_name] = section_text
        sections.append(
            {
                "section_name": section_name,
                "section_text": normalize_section_text(section_text),
                "char_count": len(section_text),
                "present": bool(section_text),
            }
        )
    return sections, raw_by_name


def normalize_section_text(section_text: str) -> str | None:
    if not section_text:
        return None
    lines = lines_from_text(section_text)
    if not lines:
        return None
    if is_section_header(lines[0]):
        lines = lines[1:]
    text = "\n".join(lines).strip()
    return text or None


def parse_activity(activity: str) -> tuple[str | None, str | None]:
    if "--" in activity:
        main, sub = activity.split("--", 1)
        return normalize_text_value(main), normalize_text_value(sub)
    return normalize_text_value(activity), None


def _with_entities(row: dict, text: str) -> dict:
    entities = extract_entities(text)
    row["ner_entities"] = json.dumps(entities, ensure_ascii=False)
    row["ner_depths"] = json.dumps(entities["depths"], ensure_ascii=False)
    row["ner_equipment"] = json.dumps(entities["equipment"], ensure_ascii=False)
    row["ner_measurements"] = json.dumps(entities["measurements"], ensure_ascii=False)
    row["ner_time_refs"] = json.dumps(entities["time_refs"], ensure_ascii=False)
    return row


def parse_operations(section_text: str) -> list[dict]:
    if not section_text:
        return []
    rows = parse_operations_from_row_lines(section_text)
    if rows:
        return rows
    return parse_operations_from_token_lines(section_text)


def _operation_row(start_time: str, end_time: str, end_depth: object, activity: str, state: str | None, remark: str) -> dict | None:
    main_activity, sub_activity = parse_activity(activity)
    if not main_activity or not remark or is_section_header(remark):
        return None
    row = {
        "start_time": start_time,
        "end_time": end_time,
        "end_depth_mmd": normalize_number(end_depth),
        "main_activity": main_activity,
        "sub_activity": sub_activity,
        "state": state,
        "remark": remark,
        "activity_label": classify_activity(f"{main_activity} {sub_activity or ''} {remark}"),
    }
    return _with_entities(row, remark)


def _split_activity_state_remark(text: str) -> tuple[str, str | None, str]:
    match = re.search(r"\s(ok|nok|na|n/a)\s", f" {text} ", flags=re.IGNORECASE)
    if not match:
        return text.strip(), None, ""
    start = match.start(1) - 1
    end = match.end(1) - 1
    activity = text[:start].strip()
    state = text[start:end].strip().lower()
    remark = text[end:].strip()
    return activity, state, remark


def parse_operations_from_row_lines(section_text: str) -> list[dict]:
    lines = lines_from_text(section_text)
    row_start = re.compile(r"^(\d{2}:\d{2})\s+(\d{2}:\d{2})\s+(-?\d+(?:[.,]\d+)?)\s+(.+)$")
    pending: dict | None = None
    rows = []

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        row = _operation_row(
            pending["start_time"],
            pending["end_time"],
            pending["end_depth_mmd"],
            pending["activity"],
            pending["state"],
            compact_join(pending["remark_parts"]),
        )
        if row:
            rows.append(row)
        pending = None

    for line in lines:
        match = row_start.match(line)
        if match:
            flush()
            activity, state, remark = _split_activity_state_remark(match.group(4))
            pending = {
                "start_time": match.group(1),
                "end_time": match.group(2),
                "end_depth_mmd": match.group(3),
                "activity": activity,
                "state": state,
                "remark_parts": [remark] if remark else [],
            }
            continue
        if pending and not is_section_header(line) and not canonical_label(line).startswith(("start end", "time time", "mmd")):
            pending["remark_parts"].append(line)
    flush()
    return rows


def parse_operations_from_token_lines(section_text: str) -> list[dict]:
    tokens = lines_from_text(section_text)
    rows = []
    states = {"ok", "nok", "na", "n/a"}

    def is_row_start(idx: int) -> bool:
        return idx + 2 < len(tokens) and is_time_token(tokens[idx]) and is_time_token(tokens[idx + 1]) and is_number_token(tokens[idx + 2])

    idx = 0
    while idx < len(tokens):
        if not is_row_start(idx):
            idx += 1
            continue
        start_time = tokens[idx]
        end_time = tokens[idx + 1]
        end_depth = normalize_number(tokens[idx + 2])
        cursor = idx + 3

        activity_parts = []
        while cursor < len(tokens) and tokens[cursor].strip().lower() not in states and not is_row_start(cursor):
            activity_parts.append(tokens[cursor])
            cursor += 1

        state = None
        if cursor < len(tokens) and tokens[cursor].strip().lower() in states:
            state = tokens[cursor].strip().lower()
            cursor += 1

        remark_parts = []
        while cursor < len(tokens) and not is_row_start(cursor):
            remark_parts.append(tokens[cursor])
            cursor += 1

        activity = compact_join(activity_parts)
        remark = compact_join(remark_parts)
        row = _operation_row(start_time, end_time, end_depth, activity, state, remark)
        if row:
            rows.append(row)
        idx = cursor
    return rows


def parse_equipment_failures(section_text: str) -> list[dict]:
    if not section_text:
        return []
    tokens = lines_from_text(section_text)
    rows = []

    def is_row_start(idx: int) -> bool:
        return idx + 1 < len(tokens) and is_time_token(tokens[idx]) and is_number_token(tokens[idx + 1])

    idx = 0
    while idx < len(tokens):
        if not is_row_start(idx):
            idx += 1
            continue
        start_time = tokens[idx]
        depth_mmd = normalize_number(tokens[idx + 1])
        cursor = idx + 2

        system_parts = []
        while cursor < len(tokens) and not is_number_token(tokens[cursor]) and not is_row_start(cursor):
            system_parts.append(tokens[cursor])
            cursor += 1
        if cursor >= len(tokens):
            break

        downtime_min = normalize_number(tokens[cursor])
        cursor += 1

        repaired_time = None
        if cursor < len(tokens) and is_time_token(tokens[cursor]):
            repaired_time = tokens[cursor]
            cursor += 1

        remark_parts = []
        while cursor < len(tokens) and not is_row_start(cursor):
            remark_parts.append(tokens[cursor])
            cursor += 1

        system_class = compact_join(system_parts)
        remark = compact_join(remark_parts)
        if system_class and remark:
            row = {
                "start_time": start_time,
                "depth_mmd": depth_mmd,
                "system_class": system_class,
                "downtime_min": downtime_min,
                "repaired_time": repaired_time,
                "remark": remark,
            }
            rows.append(_with_entities(row, remark))
        idx = cursor
    return rows


def _segment_values(tokens: list[str], label: str, all_labels: set[str]) -> list[str]:
    label_key = canonical_label(label)
    start_idx = -1
    for idx, token in enumerate(tokens):
        if canonical_label(token) == label_key:
            start_idx = idx
            break
    if start_idx == -1:
        return []
    end_idx = len(tokens)
    for cursor in range(start_idx + 1, len(tokens)):
        if canonical_label(tokens[cursor]) in all_labels:
            end_idx = cursor
            break
    return [value for value in tokens[start_idx + 1 : end_idx] if value]


def parse_drilling_fluid(section_text: str) -> tuple[list[dict], list[dict]]:
    if not section_text:
        return [], []
    tokens = lines_from_text(section_text)
    labels = [
        "Sample Time",
        "Sample Point",
        "Sample Depth mMD",
        "Fluid Type",
        "Fluid Density (g/cm3)",
        "Plastic visc. (mPa.s)",
        "Yield point (Pa)",
    ]
    label_set = {canonical_label(label) for label in labels}
    segments = {label: _segment_values(tokens, label, label_set) for label in labels}
    n_rows = max([0] + [len(values) for values in segments.values()])
    rows = []
    checks = []

    def pick(values: list[str], idx: int) -> str | None:
        if idx < len(values):
            return values[idx]
        return None

    for idx in range(n_rows):
        raw = {
            "sample_time": pick(segments["Sample Time"], idx),
            "sample_point": pick(segments["Sample Point"], idx),
            "sample_depth_mmd": pick(segments["Sample Depth mMD"], idx),
            "fluid_type": pick(segments["Fluid Type"], idx),
            "fluid_density_g_cm3": pick(segments["Fluid Density (g/cm3)"], idx),
            "plastic_viscosity_mpa_s": pick(segments["Plastic visc. (mPa.s)"], idx),
            "yield_point_pa": pick(segments["Yield point (Pa)"], idx),
        }
        row = {
            "sample_time": raw["sample_time"] if is_time_token(raw["sample_time"]) else None,
            "sample_point": normalize_text_value(raw["sample_point"]),
            "sample_depth_mmd": normalize_number(raw["sample_depth_mmd"]),
            "fluid_type": normalize_text_value(raw["fluid_type"]),
            "fluid_density_g_cm3": normalize_number(raw["fluid_density_g_cm3"]),
            "plastic_viscosity_mpa_s": normalize_number(raw["plastic_viscosity_mpa_s"]),
            "yield_point_pa": normalize_number(raw["yield_point_pa"]),
        }
        non_empty_values = [value for value in row.values() if not is_missing_text(value)]
        if not non_empty_values:
            continue
        if len(non_empty_values) < 3:
            checks.append(
                {
                    "table_name": "drilling_fluid",
                    "field_name": None,
                    "severity": "warning",
                    "check_name": "partial_fluid_row",
                    "message": f"Partial drilling fluid row retained at row offset {idx}",
                }
            )
        rows.append(row)
    return rows, checks


def build_report_sections_columns(report: dict, raw_sections: dict[str, str]) -> None:
    report["summary_activities_24h"] = normalize_section_text(raw_sections.get("summary_activities_24h", ""))
    report["summary_planned_24h"] = normalize_section_text(raw_sections.get("summary_planned_24h", ""))
    report["operations_section_raw"] = raw_sections.get("operations") or None
    report["equipment_failure_section_raw"] = raw_sections.get("equipment_failure") or None
    report["drilling_fluid_section_raw"] = raw_sections.get("drilling_fluid") or None


def has_bad_marker(value: object) -> bool:
    return isinstance(value, str) and bool(re.search(r"summary of activities|summary of planned activities", value, re.I))
