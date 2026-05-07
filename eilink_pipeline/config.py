from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    root: Path
    pdf_dir: Path
    nds_path: Path
    db_path: Path
    output_dir: Path

    @classmethod
    def from_root(cls, root: Path | str) -> PipelineConfig:
        root_path = Path(root).resolve()
        return cls(
            root=root_path,
            pdf_dir=root_path / "PDF_version_1000",
            nds_path=root_path / "nds_events.xlsx",
            db_path=root_path / "ei_reports.db",
            output_dir=root_path / "outputs",
        )


DEFAULT_CONFIG = PipelineConfig.from_root(Path(__file__).resolve().parents[1])
