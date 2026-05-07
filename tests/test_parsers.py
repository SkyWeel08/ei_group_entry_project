from eilink_pipeline.parsers import extract_labeled_value, parse_drilling_fluid, parse_metadata, parse_operations


def test_metadata_stops_at_next_label_instead_of_stealing_later_values():
    text = "\n".join(
        [
            "Operator:",
            "Rig Name:",
            "BYFORD DOLPHIN",
            "Drilling contractor:",
            "Spud Date:",
            "1997-07-25",
        ]
    )
    report, checks = parse_metadata(text)
    assert report["operator"] is None
    assert report["rig_name"] == "BYFORD DOLPHIN"
    assert any(check["field_name"] == "operator" for check in checks)


def test_extract_labeled_value_reads_next_non_label_value():
    value, reason = extract_labeled_value(["Wellbore:", "15/9-F-10"], ["Wellbore"])
    assert value == "15/9-F-10"
    assert reason is None


def test_parse_operations_adds_activity_and_entities():
    section = "\n".join(
        [
            "Operations",
            "00:00",
            "02:00",
            "246",
            "drilling -- drill",
            "ok",
            "Reamed interval 222-246 m MD, 3500 lpm, 95 bar, 140 RPM.",
        ]
    )
    rows = parse_operations(section)
    assert len(rows) == 1
    assert rows[0]["activity_label"] == "CUT"
    assert "95 bar" in rows[0]["ner_measurements"]


def test_parse_drilling_fluid_drops_empty_and_sentinel_rows():
    section = "\n".join(
        [
            "Drilling Fluid",
            "Sample Time",
            "00:00",
            "06:00",
            "Sample Point",
            "Active pit",
            "",
            "Sample Depth mMD",
            "2310",
            "-999.99",
            "Fluid Type",
            "ULTIDRILL",
            "",
            "Fluid Density (g/cm3)",
            "1.50",
            "-999.99",
            "Plastic visc. (mPa.s)",
            "41",
            "",
            "Yield point (Pa)",
            "10",
            "",
        ]
    )
    rows, checks = parse_drilling_fluid(section)
    assert rows
    assert rows[0]["fluid_density_g_cm3"] == 1.5
    assert all(row["fluid_density_g_cm3"] != -999.99 for row in rows)
    assert checks
