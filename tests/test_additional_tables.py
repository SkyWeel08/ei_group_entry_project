from eilink_pipeline.additional_tables import _rows_to_dicts, _safe_table_filename


def test_rows_to_dicts_parses_title_row_and_values():
    rows = [
        ["Pore Pressure", "", ""],
        ["Time", "Depth mMD", "Reading"],
        ["00:00", "2213", "estimated"],
        ["06:00", "2220", "measured"],
    ]
    parsed = _rows_to_dicts("Pore Pressure", rows)
    assert len(parsed) == 2
    assert parsed[0]["Time"] == "00:00"
    assert parsed[0]["Depth mMD"] == "2213"
    assert parsed[1]["Reading"] == "measured"


def test_safe_table_filename_slugifies_name():
    assert _safe_table_filename("Pore Pressure") == "pore_pressure.csv"
    assert _safe_table_filename("Gas Reading Information") == "gas_reading_information.csv"


def test_casing_liner_tubing_is_transposed_to_entry_rows():
    rows = [
        ["Start Time", "06:00", "06:00"],
        ["End Time", "12:15", "12:15"],
        ["Type of Pipe", "Casing", "Casing"],
        ["Casing Type", "Top", "Top"],
        ["Outside diameter (in)", "30", "30"],
        ["Inside diameter (i n)", "28", "27"],
        ["Weight (lbm/ft)", "456.6", "309.7"],
        ["Grade", "X-65", "X-52"],
        ["Top mMD", "139.7", "165.1"],
        ["Bottom mMD", "165.1", "201.7"],
    ]
    parsed = _rows_to_dicts("Casing Liner Tubing", rows)
    assert len(parsed) == 2
    assert parsed[0]["start_time"] == "06:00"
    assert parsed[0]["end_time"] == "12:15"
    assert parsed[0]["inside_diameter_in"] == "28"
    assert parsed[0]["weight_lbm_ft"] == "456.6"
    assert parsed[1]["weight_lbm_ft"] == "309.7"
