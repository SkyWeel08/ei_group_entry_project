from eilink_pipeline.text_utils import normalize_datetime, normalize_number, split_period


def test_normalize_number_rejects_section_markers_and_sentinels():
    assert normalize_number("Summary of activities (24 Hours)") is None
    assert normalize_number("-999.99") is None
    assert normalize_number("1,73 g/cm3") == 1.73


def test_datetime_and_period_normalization():
    assert normalize_datetime("2009-04-06 06:00") == "2009-04-06 06:00"
    assert split_period("2009-04-11 00:00 - 2009-04-12 00:00") == ("2009-04-11 00:00", "2009-04-12 00:00")
