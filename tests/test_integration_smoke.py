from pathlib import Path

from eilink_pipeline.config import PipelineConfig
from eilink_pipeline.extraction import build_corpus


def test_small_pdf_subset_has_required_tables_and_clean_numeric_markers():
    root = Path(__file__).resolve().parents[1]
    config = PipelineConfig.from_root(root)
    pdf_files = sorted(config.pdf_dir.glob("15_9_F_10_2009_04_1*.pdf"))[:2]
    reports_df, sections_df, operations_df, _equipment_df, fluid_df, quality_df = build_corpus(config, pdf_files=pdf_files, progress=False)
    assert len(reports_df) == len(pdf_files)
    assert not sections_df.empty
    assert not operations_df.empty
    assert "report_id" in quality_df.columns or quality_df.empty
    numeric_text = reports_df[["depth_current_mmd", "depth_current_mtvd"]].astype(str).to_string()
    assert "Summary of activities" not in numeric_text
    if not fluid_df.empty and "fluid_density_g_cm3" in fluid_df.columns:
        assert not fluid_df["fluid_density_g_cm3"].isin([-999.99]).any()
