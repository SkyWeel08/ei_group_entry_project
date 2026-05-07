from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedReport:
    report: dict
    sections: list[dict]
    operations: list[dict]
    equipment_failures: list[dict]
    drilling_fluid_rows: list[dict]
    quality_checks: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class MetadataField:
    labels: tuple[str, ...]
    kind: str = "text"
