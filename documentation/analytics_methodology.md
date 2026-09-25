# Phase 5 Analytics Methodology

## How it runs

- **Queries:** every analysis is a Spark SQL file in `spark_sql/analytics/`. `spark_jobs/phase5_analytics.py` runs the files in filename order and writes each result to `hdfs:///urbantransit/analytics/<name>` as Parquet. It then reads the result back and registers it as a view, so later files can query earlier results by name.
- **Reports:** `spark_jobs/phase5_report.py` turns the stored results into `reports/phase5_analytics_report.md`. `spark_jobs/verify_phase5.py` checks the Phase 5 checklist and writes `reports/phase5_verification.json`.
- **Laravel analogy:** the SQL folder is a set of named query scopes, the wrapper is the Artisan command that runs and saves them, and the report script is the controller that formats the output for people.

```bash
python spark_jobs/phase5_analytics.py            # all outputs (about 8 min)
python spark_jobs/phase5_analytics.py --only od_matrix,route_performance   # re-run some
python spark_jobs/phase5_report.py
python spark_jobs/verify_phase5.py
```

### Parameters

The SQL files contain no hard-coded thresholds. `${placeholders}` are filled from three config files:

| file | provides |
|---|---|
| `config/thresholds.yaml` | occupancy categories, bunching ratios, stop-peak z-score |
| `config/phase4.yaml` | on-time band: −2 < delay < 5 min |
| `config/phase5.yaml` | time periods and every Phase 5 threshold |

The occupancy `CASE` expression is generated directly from `thresholds.yaml`, so editing that file changes the categories everywhere.

### Inputs

Inputs are the five Phase 4 feature tables. A few facts do not exist in those tables at the grain some analyses need, so they are read from the **Phase 3 clean** tables. The raw or ingested data is never read.

| clean table | used for |
|---|---|
| `tickets`, `passengers` | tap-in/tap-out stops (O-D matrix, segmentation) |
| `delays` | stop-level delay records |
| `route_stops`, `stops` | route geometry and stop sequence |
| `service_calendar` | day types and holidays |
| `vehicles` | vehicle types and capacity |
| `passenger_counts` | `max_load_stop_id` only |

### Shared views

| view | meaning |
|---|---|
| `v_trip` | trip features plus `day_type`, `day_class` (weekday/weekend/holiday), `time_period`, `occupancy_category` and scheduled runtime. It deliberately **does not expose** the same-day peak columns (`peak_hour_indicator`, `hourly_boardings`, `daily_boardings`). |
| `v_ticket` | card journeys with their trip context, expansion factor and journey distance |
| `v_headway` | actual headway compared with the scheduled gap |
| `v_normal_days` | route-days that are neither special-event spikes/drops nor holidays |

### Time periods

Time periods are based on scheduled-departure hour:

| period | hours |
|---|---|
| early_morning | 0–6 |
| morning_peak | 7–9 |
| midday | 10–15 |
| evening_peak | 16–18 |
| evening | 19–23 |

These are only labels. Whether a period is actually a peak is decided from demand (item 4).

### Rules that apply everywhere

- **Missing measurements are never treated as 0 or normal.** Unmeasured trips have NULL boardings and occupancy, and trips that were not evaluated have NULL delay (Phase 4). Averages skip NULLs, and counts of measured trips are reported next to totals. Occupancy categories exist only for measured trips. Route-day demand uses Phase 4's `estimated_daily_boardings`, which scales measured trips up to all operated trips.
- **Tickets are a smart-card sample** of about 3–4% of riders (CMD-010). Ticket-based results are multiplied by the expansion factor from item 2 and always keep the raw `card_journeys` / `card_taps` alongside.
- **Abnormal days never define "normal".** Baselines use medians, and route judgements use only `v_normal_days` (item 17).

## 1. EDA

**Outputs:** `eda_route_demand`, `eda_stop_usage`, `eda_route_delay`, `eda_peak_hours`, `eda_peak_days`, `eda_travel_time_variation`, `eda_stop_patterns`.

- **Route demand:** the mean of `estimated_daily_boardings` per service day. Routes launched mid-year are therefore compared per day, not by annual total.
- **Stop usage:** expanded card tap-ins plus tap-outs per day the stop was open. A stop with no taps shows 0 *observed* taps, which is a real observation, not missing data.
- **Delay and punctuality per route:** evaluated trips only. The late share is the share of trips with delay ≥ 5 min; punctuality means −2 < delay < 5.
- **Peak hours:** demand per hour for each day class. Peak days are system totals per date; `routes_with_demand` is shown alongside because a route with no counted trips makes the total a lower bound.
- **Travel-time variation:** the coefficient of variation (CV) and the p10/p90 of travel time per route and direction.
- **Stop patterns:** expanded boardings (by tap-in time) and alightings (by tap-out time) per stop, day class and period. A stop is labelled origin-dominant or destination-dominant when one side is at least 1.5× the other.

## 2. Passenger flow

**Outputs:** `ticket_expansion_factor`, `flow_od_pairs`, `flow_route_load_profile`, `flow_direction_demand`.

**Expansion factor** (agreed in CMD-010, not a fixed system-wide percentage): counted boardings ÷ card tickets for each **route × month × time period**.
- Numerator and denominator come from the *same measured trips*, so trips without passenger counts affect neither side.
- A cell with fewer than 30 card tickets falls back to route × month, then to system × month. `factor_level` records which level was used.
- The factor changes by month because card adoption grows during the year.

**Other outputs:**
- `flow_od_pairs`: stop-to-stop flows across all routes.
- `flow_route_load_profile`: boardings and alightings along each route and direction, with the running on-board load.
- `flow_direction_demand`: direction split from passenger counters (all riders). The split is NULL when a cell has no counted trip.

## 3. Origin-destination matrix

**Output:** `od_matrix`, with one row per origin stop × destination stop × route × direction × tap-in time period × day class × day type.
- `service_type` = `routes.route_type` (brt / trunk / local / feeder).
- Each row carries `card_journeys` (the raw sample), `est_passengers` (card journeys × expansion factor) and `days_observed`, so small cells can be judged.
- Filter by any column, for example `WHERE route_id = 'R001' AND time_period = 'morning_peak' AND day_class = 'weekday'`.
- **Sampling limitation:** only registered smart-card journeys are included. Tickets flagged DQ16 (their trip record is missing) have no route or period and are left out.

## 4. Peak travel periods

**Outputs:** `peak_period_summary`, `peak_route_hours`, `peak_stop_hours`.

Peaks are detected from actual demand using the **leak-free** Phase 4 `peak_hour_indicator_asof`. For each route and hour it averages that hour's share of daily ridership over the previous 28 days of the same weekday/weekend type; the current day is never used.
- **Periods:** a period (morning peak, midday, evening peak, …) for each day class (weekday / weekend / holiday) is a peak when at least 50% of its trips carry the as-of flag.
- **Routes:** a route-hour is a route peak on the same 50% rule.
- **Stops:** stops have no as-of indicator, so a stop-hour is a peak when its expanded tap-ins are ≥ 1.5 standard deviations above the stop's mean hour (`thresholds.yaml` z-score).

The same-day `peak_hour_indicator` cannot be used, because `v_trip` does not expose it. `verify_phase5.py` also checks that no SQL file references it.

## 5. Overcrowding

**Outputs:** `overcrowding_trips`, `overcrowding_summary`.

Categories come from `thresholds.yaml`: a trip falls into the first category whose `max_ratio` is ≥ its occupancy.

| category | occupancy |
|---|---|
| Low | ≤ 0.40 |
| Moderate | ≤ 0.70 |
| High | ≤ 0.90 |
| Overcrowded | ≤ 1.10 |
| Critical | > 1.10 |

Trips with NULL `occupancy_pct` (no passenger count, or unknown vehicle capacity) are **excluded**, never counted as Low. `overcrowding_summary` reports `not_measured_trips` separately and computes shares over measured trips.

## 6. Persistent overcrowding

**Output:** `persistent_overcrowding`.

- **Cell:** route × direction × day of week × time period.
- **Overloaded day:** at least one measured trip in the cell that day was Overcrowded or Critical.
- **Days judged:** normal days only. Overloads on excluded event/holiday days are counted separately as `event_day_overloads`.

| pattern | rule |
|---|---|
| persistent | overloaded on ≥ 4 days **and** on ≥ 50% of observed days |
| one_off | overloaded on 1–2 days |
| recurring | anything in between |
| none | never overloaded |
| insufficient_data | fewer than 4 observed days |

## 7. Underutilized services

**Output:** `underutilized_services` (route × direction × day class × period).

| status | rule |
|---|---|
| underutilized | average occupancy < 0.25, p90 occupancy < 0.50, boardings per km below the period median, and at least 2 trips/hour |
| low_use_low_frequency | the same except fewer than 2 trips/hour. Cutting further would remove coverage, so it is reported but not recommended for cuts. |
| insufficient_data | fewer than 30 counted trips |

This takes frequency, route length (boardings per km), time period and day into account.

## 8. Route performance scoring

**Output:** `route_performance`. All metrics are **medians of daily values over normal days**.

**Component scores (0–100):**

| component | how it is scored |
|---|---|
| demand | percentile rank of median daily boardings |
| occupancy | absolute: 100 at the 0.70 target, falling linearly to 0 at 0 or 1.40 |
| punctuality | percentile rank of median punctuality |
| delay frequency | inverse rank of the late share |
| travel time | inverse rank of actual ÷ scheduled travel time |
| reliability | inverse rank of the arrival-delay standard deviation |
| load | inverse rank of p90 occupancy |
| utilisation | absolute: 1 − underload share − overload share |

The composite is a weighted mean using the weights in `phase5.yaml`. Percentile ranks are computed among eligible routes only.

**Classes** (first matching rule wins):

| class | rule |
|---|---|
| Insufficient Data | fewer than 28 normal service days (new route) or less than 50% passenger-count coverage |
| Overcrowded | at least one *persistent* overload cell (item 6) |
| High Demand but Unreliable | demand score ≥ 60 and reliability index in the bottom 40% |
| Reliable but Underutilized | reliability index in the top 40% and (demand score ≤ 40 or median underload share ≥ 50%) |
| High Performing | composite in the top 40% |
| Low Performing | composite in the bottom 40% |
| Average | the remainder (not one of the SRS classes; see *Decisions needed* in the summary) |

**Tricky cases and how they are handled:**

| case | handling |
|---|---|
| One abnormal day must not flag a route | Route metrics are medians over normal days (event spikes/drops and holidays removed). "Overcrowded" requires a *persistent* cell, so one-off and recurring overloads never flag a route; `tricky_case_notes` records how many such cells were ignored. |
| Overcrowded in one direction only | Persistence is judged per direction. `overcrowded_scope` = `direction_0_only`, `direction_1_only` or `both_directions`, so a recommendation can target one direction. |
| Overcrowded only at specific stops | Using `max_load_stop_id` of the overloaded trips: if ≥ 60% of them peak at one stop, `overcrowding_location = stop_specific` with `hotspot_stop_id`; otherwise `route_wide`. |
| New routes launched mid-year / low coverage | Marked `Insufficient Data`: not scored and not ranked against mature routes. |
| Special events and holidays | Excluded from all route baselines; the count is shown in `excluded_abnormal_days`. |

## 9. Delay analysis

**Outputs:** `delay_by_dimension`, `delay_by_stop`, `delay_congestion_patterns`, `delay_accumulation`, `delay_stop_position_profile`, `delay_consistent_entities`, `delay_top_trips`.

Two delay measures are used:

| measure | coverage | used for |
|---|---|---|
| `delay_minutes` | evaluated trips only (exception log, see `feature_catalog.md`) | dimensions, top trips, consistency |
| `arrival_delay_min` | every completed trip | congestion patterns and accumulation, where the 0 inside the tolerance band would hide small effects |

- **By dimension:** delay by route, vehicle, hour, day of week, direction, time period, day class, distance band and route type, in one long table.
- **By trip:** the 500 most delayed evaluated trips.
- **By stop:** late delay records per stop divided by *exposure*, the number of operated trips on every route and direction serving the stop. A **bottleneck stop** is in the top 5% by congestion-record rate (reasons junction_bottleneck, traffic_congestion or passenger_boarding) with at least 50 records.
- **Congestion patterns:** weekday mean arrival delay in each peak compared with midday. A difference of ≥ 1 min gives morning, evening or both-peaks congestion.
- **Accumulation:** arrival delay at the last stop minus departure deviation at the first stop, per route, direction and period. The stop-position profile shows where along the route late records occur (in deciles).
- **Consistently delayed routes and vehicles:** the entity's daily late share is above the *same day's* system late share on ≥ 75% of its days (at least 20 days; vehicles need ≥ 100 evaluated trips). Comparing with the same day removes city-wide bad days such as fog or protests.

## 10. Stop performance

**Output:** `stop_performance`. One row per stop, with:
- boardings, alightings and turnover (expanded card taps per open day)
- routes serving the stop (connectivity) and trips serving it per day (frequency)
- turnover per trip
- late-record rate, average recorded delay and top delay reason
- weekday boardings by period
- the bottleneck flag from item 9

## 11. Travel-time analysis

**Outputs:** `travel_time_analysis`, `travel_time_peak_offpeak`.

- Scheduled runtime (`scheduled_arrival − scheduled_departure`) compared with actual travel time, per route, direction, day class and period.
- `historical_avg_min` is the route-direction's trip-weighted mean over the whole year, and `vs_historical_min` is each cell's deviation from it.
- Weekday peak (morning + evening peak) compared with off-peak travel time, both actual and scheduled, including `peak_penalty_pct`.

## 12. Route reliability

**Output:** `route_reliability`, one row per route:
- % on time (evaluated trips)
- delay variation (std of arrival delay)
- missed schedules (cancelled share)
- early arrivals (arrival delay ≤ −2) and late arrivals (≥ 5)
- travel-time consistency (mean CV within route/direction/day class/period)

## 13. Schedule adherence

**Output:** `schedule_adherence`, per route and day class:
- early / on-time / late arrivals from `arrival_delay_min` against the −2..5 min band
- missed trips (cancelled)
- irregular intervals: headways classed as bunched or gap (item 14) as a share of assessed intervals

## 14. Headway analysis and bunching

**Output:** `headway_bunching`.

Actual headway (Phase 4: time since the previous *operated* trip on the same route, day and direction) is compared with the **scheduled gap to that same previous trip**.

| status | rule (`thresholds.yaml`) |
|---|---|
| bunched | ratio < 0.5 |
| service gap | ratio > 1.5 |
| not assessed | scheduled gap < 3 min |

Overtakings (negative headways, flagged in Phase 4) are counted as the extreme form of bunching.

## 15. Service frequency

**Output:** `service_frequency`, per route × direction × day class × period. Scheduled trips per hour are compared with boardings, occupancy, the as-of peak rate and delay.

| verdict | rule |
|---|---|
| too_little | average occupancy ≥ 0.85, or ≥ 20% of counted trips Overcrowded/Critical |
| too_much | average occupancy < 0.30, p90 < 0.50 and at least 2 trips/hour |
| well_matched | everything else |
| insufficient_data | fewer than 30 counted trips |

## 16. Demand-supply gap and capacity optimisation

**Output:** `demand_supply_gap`.

Utilisation at the peak load point = Σ max_load ÷ Σ capacity (counted trips with known capacity).

| status | rule |
|---|---|
| excess_demand | utilisation ≥ 0.90, or ≥ 1 denied boarding per trip |
| excess_supply | utilisation < 0.30 |
| balanced | everything else |

Required capacity = p90 max_load ÷ 0.85 target load. The **suggested vehicle type** is the smallest type in `vehicles` whose capacity is at least that. The suggestion is chosen as follows:

| suggestion | when |
|---|---|
| larger_vehicle | excess demand and a bigger type fits |
| add_trips | excess demand and no type is big enough; `extra_trips_per_hour` is sized with the largest type |
| smaller_vehicle | excess supply and a smaller type fits |
| reduce_frequency | excess supply otherwise |
| no_change | balanced |

## 17. Special event detection

**Outputs:** `special_event_route_days`, `special_event_dates`.

- **Baseline:** each route-day's estimated demand is compared with the **median** demand of the same route, same weekday and **same calendar day type** (weekday / ramadan_weekday / saturday / sunday / holiday) over the previous 8 weeks, excluding the current week.
  - A median is not moved by a few spike days, so **events never redefine the baseline**.
  - Matching the day type stops the reduced Ramadan timetable, or a holiday, from becoming the baseline for ordinary days. A first version without this produced false April "spikes"; see `DEV_LOG.md`.
- **Status:**

| status | rule |
|---|---|
| spike | ratio ≥ 1.5 |
| drop | ratio ≤ 0.5 |
| insufficient_history | fewer than 4 baseline days |

- **Event dates:** a date with spikes on ≥ 3 routes is a city-wide event.
- **Downstream use:** spikes, drops and holidays are removed from every downstream baseline through `v_normal_days`.
- **Validation only:** `event_extra_trips` (generator-scheduled event trips) is shown to check the detector. Detection itself uses demand alone.

## 18. Anomaly detection

**Outputs:** `anomalies` (long format: type, entity, date, observed, expected, detail) and `anomaly_summary`.

| anomaly_type | rule |
|---|---|
| demand_spike / demand_drop | route-day vs robust baseline (item 17) |
| abnormal_delay | recorded trip delay ≥ 60 min |
| impossible_occupancy | max_load > boardings, or denied boardings while the bus is under half full |
| abnormal_travel_time | actual ÷ scheduled runtime < 0.5 or > 2.0 |
| unexpected_route_usage | card tap at a stop that is not on the trip's route |
| duplicate_ticketing_signal | same card taps in again at the **same stop** within 120 s, or taps in before its previous journey ended (Phase 3 already removed exact duplicates; a quick tap at a *different* stop is a normal transfer) |
| irregular_stop_activity | stop-day card taps ≥ 3× or ≤ 0.2× the stop's same-weekday median (baseline ≥ 20) |

A type with zero signals, for example impossible occupancy after Phase 3 quarantined capacity violations, is a valid result and simply does not appear in the summary.

## 19. Passenger segmentation

**Outputs:** `passenger_segments` (one row per card holder) and `segment_summary`.

Segments are built from each card holder's ticket history: active days per week over their own active span, weekday share, weekend share, peak share (tap-in time) and average journey km. Rules are applied in this order, and the first match wins:

| order | segment | rule |
|---|---|---|
| 1 | Daily Commuter | ≥ 3 active days/week and ≥ 80% weekday journeys |
| 2 | Weekend Traveller | ≥ 50% of journeys on weekends |
| 3 | Long-Distance Traveller | average journey km ≥ the 80th percentile of card holders |
| 4 | Peak-Hour Traveller | ≥ 70% of journeys in peak periods |
| 5 | Occasional Traveller | everyone else |

**Sampling limitation:**
- Tickets cover **registered smart-card holders only**, about 3–4% of riders. Cash riders cannot be segmented at all.
- Card adoption grows during the year, so late adopters have short histories. Using each person's own active span reduces this bias.
- Segment sizes are counts of **card holders**, not of the population. The expansion factor scales *journeys* (`share_of_est_journeys`), never people.
- Tickets flagged DQ15 (passenger not registered) cannot be attributed to a person and are excluded.
