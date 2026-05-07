from __future__ import annotations

import math
import re
from collections.abc import Iterable
from datetime import datetime

SECTION_HEADERS = {
    "summary of activities",
    "summary of activities 24 hours",
    "summary of activities 24h",
    "summary of planned activities",
    "summary of planned activities 24 hours",
    "summary of planned activities 24h",
    "operations",
    "equipment failure",
    "equipment failure information",
    "drilling fluid",
    "survey station",
    "pore pressure",
    "bit record",
    "casing record",
    "bha record",
}

SENTINEL_NUMBERS = {-999.99, -999.9, -999.0, -99999.0}


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def lines_from_text(text: str) -> list[str]:
    lines = [ln.strip() for ln in clean_text(text).splitlines()]
    return [ln for ln in lines if ln]


def canonical_label(value: str) -> str:
    value = value.lower().replace(":", "")
    value = value.replace("³", "3").replace("і", "3")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_section_header(value: str | None) -> bool:
    if not value:
        return False
    canonical = canonical_label(value)
    return canonical in SECTION_HEADERS or any(canonical.startswith(f"{header} ") for header in SECTION_HEADERS)


def is_time_token(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"\d{2}:\d{2}", value.strip()))


def is_number_token(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"-?\d+(?:[.,]\d+)?", value.strip()))


def is_missing_text(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if not isinstance(value, str):
        return False
    return value.strip() == "" or value.strip().lower() in {"none", "nan", "n/a", "na", "-"}


def normalize_text_value(value: object) -> str | None:
    if is_missing_text(value):
        return None
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    if is_section_header(text):
        return None
    return text


def normalize_number(value: object, *, allow_zero: bool = True) -> float | None:
    if is_missing_text(value):
        return None
    text = str(value).strip().replace(",", ".")
    if is_section_header(text):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    if number in SENTINEL_NUMBERS:
        return None
    if not allow_zero and number == 0:
        return None
    return number


def normalize_integer(value: object) -> int | None:
    number = normalize_number(value)
    if number is None:
        return None
    return int(number)


def normalize_flag(value: object) -> str | None:
    text = normalize_text_value(value)
    if text is None:
        return None
    upper = text.upper()
    if upper in {"Y", "YES", "TRUE", "1"}:
        return "Y"
    if upper in {"N", "NO", "FALSE", "0"}:
        return "N"
    return None


def normalize_datetime(value: object) -> str | None:
    text = normalize_text_value(value)
    if text is None:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?", text)
    if not match:
        return None
    raw = match.group(0)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M" if "%H" in fmt else "%Y-%m-%d")
        except ValueError:
            continue
    return None


def split_period(period_text: object) -> tuple[str | None, str | None]:
    text = normalize_text_value(period_text)
    if text is None:
        return None, None
    match = re.search(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*-\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
        text,
    )
    if not match:
        return None, None
    return match.group(1), match.group(2)


def extract_section(text: str, start_markers: Iterable[str], end_markers: Iterable[str]) -> str:
    low = text.lower()
    start_idx = -1
    for marker in start_markers:
        idx = low.find(marker.lower())
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
    if start_idx == -1:
        return ""

    end_idx = len(text)
    for marker in end_markers:
        idx = low.find(marker.lower(), start_idx + 1)
        if idx != -1:
            end_idx = min(end_idx, idx)
    return text[start_idx:end_idx].strip()


def compact_join(parts: Iterable[object]) -> str:
    text = " ".join(str(part) for part in parts if not is_missing_text(part))
    return re.sub(r"\s+", " ", text).strip()
