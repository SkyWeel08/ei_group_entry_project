from __future__ import annotations

import re

ACTIVITY_RULES = [
    ("TRIP_IN", ["rih", "run in hole", "ran in", "tih", "trip in"]),
    ("TRIP_OUT", ["pooh", "pull out of hole", "pulled out", "trip out"]),
    ("CEMENT", ["cement", "stinger", "woc"]),
    ("PRESSURE_TEST", ["pressure test", "fit test", "leak test", "test bop"]),
    ("EQUIPMENT_FAILURE", ["failure", "failed", "break", "leak", "downtime", "not fit"]),
    ("REPAIR", ["repair", "fixed", "replaced", "removed", "corrective"]),
    ("WAIT", ["wait", "woc", "stand by", "standby", "hold"]),
    ("CIRCULATE", ["circulate", "circulated", "sweep", "conditioning"]),
    ("FISHING", ["fishing", "junk", "spear", "stuck"]),
    ("CUT", ["drill", "drilled", "ream", "cut", "mill", "milled"]),
]

EQUIPMENT_DICTIONARY = sorted(
    [
        "flx packer",
        "tds",
        "bop",
        "xo",
        "spear bha",
        "bha",
        "mwd",
        "ubho",
        "top drive",
        "iron roughneck",
        "elevator",
        "casing running equipment",
        "ontrack",
        "prs",
        "rov",
        "stinger",
        "dc",
        "hwdp",
        "bit",
        "pipe handler",
        "slips",
        "packer",
        "casing",
    ],
    key=len,
    reverse=True,
)


def unique(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def extract_entities(text: object) -> dict[str, list[str]]:
    if not isinstance(text, str):
        text = ""
    lower = text.lower()
    depths = re.findall(r"\b\d+(?:[.,]\d+)?\s*(?:mmd|mtvd|md|tvd|m)\b", lower, flags=re.IGNORECASE)
    time_refs = re.findall(r"\b\d{1,2}:\d{2}\b", lower)

    measurements = []
    for pattern in [
        r"\b\d+(?:[.,]\d+)?\s*rpm\b",
        r"\b\d+(?:[.,]\d+)?\s*bar\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:lpm|l/min)\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:mt|ton|tons)\b",
        r"\b\d+(?:[.,]\d+)?\s*knm\b",
        r"\b\d+(?:[.,]\d+)?\s*m3\b",
    ]:
        measurements.extend(re.findall(pattern, lower, flags=re.IGNORECASE))

    equipment = []
    for item in EQUIPMENT_DICTIONARY:
        if re.search(rf"\b{re.escape(item)}\b", lower):
            equipment.append(item)

    return {
        "depths": unique(depths),
        "equipment": unique(equipment),
        "measurements": unique(measurements),
        "time_refs": unique(time_refs),
    }


def classify_activity(text: object) -> str:
    if not isinstance(text, str):
        return "OTHER"
    lower = text.lower()
    for label, keywords in ACTIVITY_RULES:
        if any(keyword in lower for keyword in keywords):
            return label
    return "OTHER"
