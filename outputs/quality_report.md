# eiLink Pipeline Quality Report

## Run Summary

```json
{
  "reports_total": 1000,
  "operations_total": 10597,
  "equipment_failures_total": 240,
  "drilling_fluid_rows_total": 2830,
  "keywords_rows_total": 11988,
  "nds_events_total": 4,
  "nds_events_matched": 3,
  "quality_checks_total": 5952,
  "db_path": "C:\\Users\\wlf01\\Downloads\\RA DS - 2026\\Task_DS\\ei_group_entry_project\\ei_reports.db"
}
```

## Table Counts

| Table | Rows |
| --- | ---: |
| reports | 1000 |
| report_sections | 5000 |
| operations | 10597 |
| equipment_failures | 240 |
| drilling_fluid | 2830 |
| report_keywords | 11988 |
| nds_event_matches | 4 |
| parse_quality_checks | 5952 |

## Quality Checks

- Total checks: 5952
- Severity counts: `{"info": 4325, "warning": 1627}`

| Severity | Table | Field | Check | Message |
| --- | --- | --- | --- | --- |
| info | reports | operator | value_missing_before_next_label | No accepted value for operator |
| info | reports | rig_name | value_missing_before_next_label | No accepted value for rig_name |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| warning | reports | depth_current_mmd | metadata_value_rejected | Rejected raw value '-999.99' for depth_current_mmd |
| info | reports | depth_current_mtvd | value_missing_before_next_label | No accepted value for depth_current_mtvd |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mmd | value_missing_before_next_label | No accepted value for depth_last_casing_mmd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | depth_formation_strength_mmd | value_missing_before_next_label | No accepted value for depth_formation_strength_mmd |
| info | reports | depth_formation_strength_mtvd | value_missing_before_next_label | No accepted value for depth_formation_strength_mtvd |
| info | reports | plug_back_depth_mmd | value_missing_before_next_label | No accepted value for plug_back_depth_mmd |
| info | reports | pressure_test_type | value_missing_before_next_label | No accepted value for pressure_test_type |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| warning | reports | depth_current_mmd | metadata_value_rejected | Rejected raw value '-999.99' for depth_current_mmd |
| info | reports | depth_current_mtvd | value_missing_before_next_label | No accepted value for depth_current_mtvd |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | depth_formation_strength_mmd | value_missing_before_next_label | No accepted value for depth_formation_strength_mmd |
| info | reports | depth_formation_strength_mtvd | value_missing_before_next_label | No accepted value for depth_formation_strength_mtvd |
| info | reports | pressure_test_type | value_missing_before_next_label | No accepted value for pressure_test_type |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | plug_back_depth_mmd | value_missing_before_next_label | No accepted value for plug_back_depth_mmd |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | plug_back_depth_mmd | value_missing_before_next_label | No accepted value for plug_back_depth_mmd |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 3 |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 4 |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| warning | reports | depth_current_mmd | metadata_value_rejected | Rejected raw value '-999.99' for depth_current_mmd |
| info | reports | depth_current_mtvd | value_missing_before_next_label | No accepted value for depth_current_mtvd |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 3 |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 4 |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | plug_back_depth_mmd | value_missing_before_next_label | No accepted value for plug_back_depth_mmd |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 3 |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 4 |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |
| info | reports | depth_kickoff_mtvd | value_missing_before_next_label | No accepted value for depth_kickoff_mtvd |
| info | reports | depth_last_casing_mtvd | value_missing_before_next_label | No accepted value for depth_last_casing_mtvd |
| info | reports | plug_back_depth_mmd | value_missing_before_next_label | No accepted value for plug_back_depth_mmd |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 3 |
| warning | drilling_fluid |  | partial_fluid_row | Partial drilling fluid row retained at row offset 4 |
| info | reports | drilling_contractor | value_missing_before_next_label | No accepted value for drilling_contractor |

## NDS Matching

| Event | Well | Matched | PDF | Ensemble | Reason |
| ---: | --- | --- | --- | ---: | --- |
| 1 | 15/9-F-10 | True | 15_9_F_10_2009_04_12.pdf | 0.3476 | Matched by ensemble benchmark (word TF-IDF + char TF-IDF + fuzzy + BM25 + keyword overlap). |
| 2 | 15/9-F-11 | True | 15_9_F_11_2013_03_17.pdf | 0.1485 | Matched by ensemble benchmark (word TF-IDF + char TF-IDF + fuzzy + BM25 + keyword overlap). |
| 3 | 15/9-F-12 | True | 15_9_F_12_2007_06_23.pdf | 0.2957 | Matched by ensemble benchmark (word TF-IDF + char TF-IDF + fuzzy + BM25 + keyword overlap). |
| 4 | 15/9-F-13 | False |  | 0.0000 | No candidate operations found for this well. |
