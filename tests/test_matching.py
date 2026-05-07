import pandas as pd

from eilink_pipeline.matching import match_nds_events


def test_nds_matching_scores_and_reports_unmatched_wells():
    reports = pd.DataFrame(
        [
            {"report_id": 1, "pdf_name": "a.pdf", "wellbore_id": "15/9-F-10"},
        ]
    )
    operations = pd.DataFrame(
        [
            {
                "operation_id": 1,
                "report_id": 1,
                "main_activity": "drilling",
                "sub_activity": "ream",
                "remark": "Reduced inclination from 0.53 deg to 0.16 deg while reaming interval.",
            }
        ]
    )
    nds = pd.DataFrame(
        [
            {"Well": "15/9-F-10", "Event": "Reduced inclination to 0.16 deg"},
            {"Well": "15/9-F-13", "Event": "differential stuck"},
        ]
    )
    matches = match_nds_events(nds, reports, operations)
    assert bool(matches.loc[0, "matched"]) is True
    assert matches.loc[0, "matched_pdf"] == "a.pdf"
    assert bool(matches.loc[1, "matched"]) is False
    assert "No candidate" in matches.loc[1, "reason"]
