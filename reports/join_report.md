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

## Chronological splits

[
  {
    "split": "train",
    "min_date": "2025-09-01",
    "max_date": "2026-05-02",
    "rows": 1433507
  },
  {
    "split": "validation",
    "min_date": "2026-05-03",
    "max_date": "2026-07-02",
    "rows": 344428
  },
  {
    "split": "test",
    "min_date": "2026-07-03",
    "max_date": "2026-08-31",
    "rows": 319222
  }
]

## Target distribution

[
  {
    "split": "test",
    "delay_severity": "Major",
    "crowding_flag": null,
    "count": 9
  },
  {
    "split": "test",
    "delay_severity": "Major",
    "crowding_flag": false,
    "count": 30658
  },
  {
    "split": "test",
    "delay_severity": "Major",
    "crowding_flag": true,
    "count": 6113
  },
  {
    "split": "test",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 141
  },
  {
    "split": "test",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 11
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 10
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 43764
  },
  {
    "split": "test",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 4996
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 48
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 218049
  },
  {
    "split": "test",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 12901
  },
  {
    "split": "test",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 1710
  },
  {
    "split": "test",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 812
  },
  {
    "split": "train",
    "delay_severity": "Major",
    "crowding_flag": null,
    "count": 22
  },
  {
    "split": "train",
    "delay_severity": "Major",
    "crowding_flag": false,
    "count": 121429
  },
  {
    "split": "train",
    "delay_severity": "Major",
    "crowding_flag": true,
    "count": 26822
  },
  {
    "split": "train",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 611
  },
  {
    "split": "train",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 89
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 37
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 169233
  },
  {
    "split": "train",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 27202
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 243
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 997288
  },
  {
    "split": "train",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 73738
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": null,
    "count": 3
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 12838
  },
  {
    "split": "train",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 3952
  },
  {
    "split": "validation",
    "delay_severity": "Major",
    "crowding_flag": null,
    "count": 14
  },
  {
    "split": "validation",
    "delay_severity": "Major",
    "crowding_flag": false,
    "count": 22376
  },
  {
    "split": "validation",
    "delay_severity": "Major",
    "crowding_flag": true,
    "count": 5519
  },
  {
    "split": "validation",
    "delay_severity": "Minor",
    "crowding_flag": false,
    "count": 138
  },
  {
    "split": "validation",
    "delay_severity": "Minor",
    "crowding_flag": true,
    "count": 12
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": null,
    "count": 12
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": false,
    "count": 40904
  },
  {
    "split": "validation",
    "delay_severity": "Moderate",
    "crowding_flag": true,
    "count": 5303
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": null,
    "count": 50
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": false,
    "count": 253423
  },
  {
    "split": "validation",
    "delay_severity": "On Time",
    "crowding_flag": true,
    "count": 13943
  },
  {
    "split": "validation",
    "delay_severity": "Severe",
    "crowding_flag": false,
    "count": 1898
  },
  {
    "split": "validation",
    "delay_severity": "Severe",
    "crowding_flag": true,
    "count": 836
  }
]

## Leakage check

`historical_*` windows order by `scheduled_departure, trip_id` and end at `rowsBetween(..., -1)`: the current and future trips are excluded. `spark_jobs/verify_phase4.py` recomputes this on a deterministic sample.
