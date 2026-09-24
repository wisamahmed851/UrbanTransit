# Cleaning Rules

_Generated from `config/data_quality.yaml` by `spark_jobs/cleaning_report.py` - edit the YAML, not this file._

Every data-quality rule has exactly one cleaning action:

| action | meaning |
|---|---|
| **correct** | replace the value with a *deterministic* derivation from other fields (never a guess); if that is impossible the row gets the rule's **fallback** action |
| **flag** | keep the row, add the rule ID to its `dq_flags` column so analyses can include or exclude it |
| **remove** | drop the row - only used for exact duplicates of a row that is kept |
| **quarantine** | move the row to `/urbantransit/clean_quarantine/<table>/` with its original content; it cannot be trusted or fixed |

Principle: prefer **flag** or **quarantine** whenever a correction would be a guess. Every action is written to the cleaning log (`/urbantransit/cleaning_log/`, Parquet): record key, issue, rule, original value, corrected value, final status.

| rule | defect type | table | severity | action | correction | fallback | rationale |
|---|---|---|---|---|---|---|---|
| DQ01 | missing_ticket_records | passenger_counts | medium | **flag** | - | - | The missing ticket rows cannot be recreated (we do not know who tapped in or where), but the counted trip is real: flag the passenger_counts row so O-D analyses know tickets are incomplete for that trip. |
| DQ02a | missing_route_ids | tickets | high | **correct** | method=lookup, via_column=trip_id, lookup_table=trips, lookup_key=trip_id, lookup_value=route_id | flag | Every ticket belongs to a trip and every trip has exactly one route, so the route can be looked up from the ticket's trip (deterministic, not a guess). If the trip is unknown or has no route, flag. |
| DQ02b | missing_route_ids | trips | high | **correct** | method=lookup, via_column=schedule_id, lookup_table=schedules, lookup_key=schedule_id, lookup_value=route_id | flag | A trip's schedule row belongs to exactly one route, so the route can be looked up from schedule_id. Otherwise flag. |
| DQ03a | invalid_stop_ids | tickets | high | **quarantine** | - | - | Tickets are used for origin-destination analysis; an unknown tap-in/tap-out stop cannot be repaired, so the row is quarantined. |
| DQ03b | invalid_stop_ids | delays | medium | **flag** | - | - | The delay value itself is still valid for trip/route delay analysis; only the stop reference is unusable. Flag and keep. |
| DQ04 | duplicate_tickets | tickets | high | **remove** | - | - | Exact copies of the same transaction would double-count revenue and ridership. Keep one copy, remove the rest; if the copies differ, the true version is unknown and all copies are quarantined. |
| DQ05 | duplicate_trips | trips | high | **remove** | - | - | Same as DQ04 for trips: duplicate trip rows double-count service. Keep one identical copy; quarantine conflicting versions. |
| DQ06 | negative_passenger_counts | passenger_counts | critical | **quarantine** | - | - | A negative count is impossible and the true value is unknown; quarantine rather than guess. |
| DQ07 | invalid_timestamps | tickets | high | **quarantine** | - | - | A tap-in time that cannot be parsed cannot be reconstructed; the row stays quarantined. |
| DQ08a | impossible_arrival_times | delays | high | **quarantine** | - | - | An arrival days or years away from the timetable is a corrupted record; the real time is unknown. Quarantine. |
| DQ08b | impossible_arrival_times | trips | high | **quarantine** | - | - | Same as DQ08a at trip level. |
| DQ09a | departure_before_arrival | delays | medium | **flag** | - | - | The arrival (and the delay derived from it) is still usable; only the departure time is inconsistent. Flag and keep. |
| DQ09b | departure_before_arrival | trips | high | **quarantine** | - | - | A trip that arrives before it departs has no usable running time; quarantine. |
| DQ10 | vehicle_capacity_violations | passenger_counts | high | **quarantine** | - | - | A load several times the vehicle capacity is a counter error; the true load is unknown. Quarantine. |
| DQ11 | invalid_delay_values | delays | medium | **correct** | method=minutes_between, start=scheduled_arrival, end=actual_arrival | quarantine | delay_minutes is redundant: it equals actual_arrival - scheduled_arrival. When both timestamps are valid and plausible the value is recomputed exactly; otherwise quarantine. |
| DQ12 | missing_vehicle_assignments | trips | medium | **correct** | method=lookup, via_column=trip_id, lookup_table=passenger_counts, lookup_key=trip_id, lookup_value=vehicle_id | flag | The on-board passenger counter reports which vehicle ran the trip, so the vehicle can be taken from passenger_counts for the same trip. If there is no count record, flag. |
| DQ13 | broken_stop_sequences | route_stops | high | **correct** | method=resequence, order_by=distance_from_start_km | - | The order of stops is defined by their distance along the route, so sequence numbers are rebuilt 1..n in distance order. A gap is closed but the missing stop cannot be restored (noted in the log). |
| DQ14 | invalid_route_distances | routes | medium | **correct** | method=max_child_value, child_table=route_stops, child_key=route_id, child_value=distance_from_start_km, child_filter=direction = 0 | flag | A route's length equals the distance of its last stop in direction 0 (route_stops), so the distance is recomputed from there; if route_stops has no rows, flag. |
| DQ15 | unknown_passengers | tickets | medium | **flag** | - | - | The journey is real and still valid for route/stop demand and O-D; only passenger segmentation is impossible. Flag and keep. |
| DQ16 | missing_trip_records | trips | high | **flag** | - | - | The counts, tickets, delays and GPS pings of a missing trip are real observations; the trip record cannot be recreated. Flag the child rows so trip-level joins can exclude them. |
| DQ17 | unknown_vehicle_ids | trips | medium | **flag** | - | - | The trip happened; the vehicle is simply not registered (e.g. a new bus). Flag so capacity-based metrics skip it. |
| DQ18 | future_timestamps | tickets | high | **quarantine** | - | - | A tap-in far outside the service day cannot be trusted (clock error); quarantine. |
| DQ19 | out_of_bounds_coordinates | stops | medium | **correct** | method=swap_coordinates | flag | Swapped latitude/longitude is a common entry error and swapping back is verifiable (the result must fall inside the operating area); anything else (e.g. 0,0) is flagged. |
| DQ20 | negative_fares | tickets | medium | **flag** | - | - | A negative fare is an accounting error of unknown size; keep the journey for demand/O-D but flag it for revenue analysis. |
| DQ21 | orphan_route_ids | trips | medium | **flag** | - | - | The trip happened; the route is not in the route list (e.g. a route added later). Flag. |

## Thresholds (from `params`)

| parameter | value |
|---|---|
| timestamp_format | yyyy-MM-dd HH:mm:ss |
| capacity_violation_factor | 1.5 |
| delay_valid_min_minutes | -60 |
| delay_valid_max_minutes | 600 |
| impossible_time_gap_hours | 12 |
| route_distance_min_km | 0 |
| route_distance_max_km | 300 |
| timestamp_date_window_days | [-1, 2] |
| geo_bounds | {'lat_min': 31.2, 'lat_max': 31.8, 'lon_min': 74.0, 'lon_max': 74.6} |
| sample_rows | 5 |

## Rows quarantined at ingestion (Phase 2)

Rows that failed type parsing in Phase 2 are re-read in Phase 3. If `correct` rules repair every column that failed (for example `delay_minutes` recomputed from the two timestamps, DQ11), the row is recovered into the clean data and logged as corrected; otherwise it stays quarantined with the matching rule IDs (or `INGESTION_TYPE_FAILURE`).

## Using the flags downstream

`dq_flags` is an array column in every clean table. Examples: exclude `DQ16` rows from trip-level joins (their trip record is missing); exclude `DQ20` rows from revenue totals; exclude `DQ01` trips from O-D completeness statistics.
