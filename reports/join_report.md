# Phase 4 Join Report

| join | keys | type | left rows | output rows | orphans |
|---|---|---|---:|---:|---:|
| 01_tickets_passengers | passenger_id | left | 2,976,868 | 2,976,868 | 5,973 |
| 02_tickets_trips | trip_id | left | 2,976,868 | 2,976,868 | 6,083 |
| 03_trips_routes | route_id | left | 2,097,157 | 2,097,157 | 0 |
| 04_trips_vehicles | vehicle_id | left | 2,097,157 | 2,097,157 | 0 |
| 05_trips_schedules | schedule_id | left | 2,097,157 | 2,097,157 | 0 |
| 06_routes_route_stops | route_id | left | 118 | 3,210 | 0 |
| 07_route_stops_stops | stop_id | left | 3,210 | 3,210 | 0 |
| 08_trips_delays | trip_id | left | 2,097,157 | 2,293,303 | 1,306,513 |
| 09_trips_passenger_counts | trip_id | left | 2,097,157 | 2,097,157 | 166,203 |
| 10_stops_location | stop_id | projection | 756 | 756 | 0 |

Ticket orphans (01, 02) are exactly the rows Phase 3 flagged `DQ15` (unknown passenger) and `DQ16` (missing trip); see `documentation/feature_catalog.md`.

## Chronological splits

[
  {
    "split": "train",
    "min_date": "2025-09-01",
    "max_date": "2026-05-01",
    "dates": 243,
    "rows": 1427922
  },
  {
    "split": "validation",
    "min_date": "2026-05-02",
    "max_date": "2026-07-01",
    "dates": 61,
    "rows": 344248
  },
  {
    "split": "test",
    "min_date": "2026-07-02",
    "max_date": "2026-08-31",
    "dates": 61,
    "rows": 324987
  }
]

## Measurement coverage

{
  "delay_source": {
    "not_evaluated": 23970,
    "within_tolerance": 1283340,
    "record": 789847
  },
  "passenger_count_measured": {
    "True": 1930954,
    "False": 166203
  },
  "negative_headway_overtaking": 146
}

## Target distribution

[
  {
    "split": "test",
    "delay_severity": null,
    "crowding_flag": null,
    "count": 3178
  },
  {
    "split": "test",
    "delay_severity": null,
    "crowding_flag": false,
    "count": 250
  },
  {
    "split": "test",
    "delay_severity": null,
    "crowding_flag": true,
    "count": 41
  },
  {
    "split": "test",
    "delay_severity": "Minor",
    "crowding_flag": null,
    "count": 3536
  },
  {
    "split": "test",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 41027
  },
  {
    "split": "test",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 5102
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 2867
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 28339
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 6221
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 15672
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 203033
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 13163
  },
  {
    "split": "test",
    "delay_severity": "Severe",
    "crowding_flag": null,
    "count": 230
  },
  {
    "split": "test",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 1499
  },
  {
    "split": "test",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 829
  },
  {
    "split": "train",
    "delay_severity": null,
    "crowding_flag": null,
    "count": 15127
  },
  {
    "split": "train",
    "delay_severity": null,
    "crowding_flag": false,
    "count": 1076
  },
  {
    "split": "train",
    "delay_severity": null,
    "crowding_flag": true,
    "count": 193
  },
  {
    "split": "train",
    "delay_severity": "Minor",
    "crowding_flag": null,
    "count": 13943
  },
  {
    "split": "train",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 154967
  },
  {
    "split": "train",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 27130
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 11432
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 109988
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 26782
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 71437
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 905620
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 73470
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": null,
    "count": 1212
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 11593
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 3952
  },
  {
    "split": "validation",
    "delay_severity": null,
    "crowding_flag": null,
    "count": 3829
  },
  {
    "split": "validation",
    "delay_severity": null,
    "crowding_flag": false,
    "count": 236
  },
  {
    "split": "validation",
    "delay_severity": null,
    "crowding_flag": true,
    "count": 40
  },
  {
    "split": "validation",
    "delay_severity": "Minor",
    "crowding_flag": null,
    "count": 3340
  },
  {
    "split": "validation",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 37283
  },
  {
    "split": "validation",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 5247
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 2114
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 19882
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 5405
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 18104
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 232213
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 13852
  },
  {
    "split": "validation",
    "delay_severity": "Severe",
    "crowding_flag": null,
    "count": 182
  },
  {
    "split": "validation",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 1699
  },
  {
    "split": "validation",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 822
  }
]

## Leakage check

`historical_*` windows order by `scheduled_departure, trip_id` and end at `rowsBetween(..., -1)`; `demand_*_growth` and `peak_hour_indicator_asof` use only days before the trip's service date. `spark_jobs/verify_phase4.py` recomputes them on data truncated at a cutoff date.
