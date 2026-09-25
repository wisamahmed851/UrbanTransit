# Transport Intelligence Summary (Phase 5)

**Data:** one year of service (2025-09-01 to 2026-08-31): 118 routes, 2,097,157 trips (1,930,954 with passenger counts) and 2,976,868 smart-card tickets.

**Sources:** every figure below comes from the Parquet outputs in `/urbantransit/analytics/`, through `spark_jobs/phase5_report.py`. The full tables are in `reports/phase5_analytics_report.md` and the machine-readable headline values are in `reports/phase5_facts.json`. Methods are in `documentation/analytics_methodology.md`.

**How to read the numbers:**
- **Demand** comes from passenger counters. Trips without a count are left out, never counted as zero.
- **Ticket-based figures** (O-D, stops, segments) are a smart-card sample of about 3–4% of riders, expanded by a per route/month/period factor. The factor averages 31.2 over 6,203 route-month-period cells and ranges from 17.1 to 61.9.

## Demand

- **Busiest routes:** the four BRT lines R004 (15,115 estimated boardings/day), R001 (14,875), R002 (12,639) and R003 (12,545). The busiest non-BRT route is trunk R031 (6,601).
- **Quietest routes:** R118, a feeder launched mid-year (222.5/day over its 62 days), then feeders R092 (230.8) and R098 (247.3).
- **Busiest stop:** Mall Road GPO (S0005), with about 6,834 expanded tap-ins plus tap-outs per day. Next are Gulberg Main Boulevard (5,702) and Gaddafi Stadium (5,695).
- **Top O-D pair:** S0030 → S0029, about 360 estimated journeys/day.
- **Peaks:** measured with the leak-free as-of indicator.
  - On weekdays, the morning peak (07–09) and the evening peak (16–18) are both peaks. The evening peak is stronger (peak rate 0.89 vs 0.57), and 16:00 is the busiest hour at about 29,236 boardings.
  - On weekends and holidays, only the evening peak qualifies.
- **Busiest weekday:** Mondays average 287,815 estimated system boardings, against 128,137 on Sundays.

## Crowding

- **Overall:** 182,249 of the 1,930,954 measured trips (9.4%) were Overcrowded (62,537) or Critical (119,712). Another 1,292,258 were Low.
- **Most overcrowded route:** R097 direction 0, with 58.1% of its measured trips Overcrowded or Critical (5,553 trips). Next are R097 direction 1 (53.0%), R107 direction 1 (52.5%) and trunk R031 in both directions (51%).
- **Persistent vs one-off:** 1,462 route × direction × weekday × period cells are persistently overloaded (78 routes). Another 823 cells were overloaded only once or twice, and those do not flag a route.
- **Scope:** of the 77 routes classed Overcrowded, 62 are overcrowded in both directions, 10 only in direction 1 and 5 only in direction 0.
- **Location:** none meets the stop-specific rule (≥ 60% of overloaded trips peaking at one stop), so all 77 are route-wide.

## Reliability and delay

- **Most delayed route:** R029, with a mean recorded delay of 5.78 min and 50.8% of evaluated trips ≥ 5 min late. Next are R039 (5.66) and R012 (5.27).
- **Most punctual routes:** R102 (84.6% of trips within −2..5 min), then R093 (84.0%) and R105 (82.7%).
- **Busiest routes are among the least punctual:** BRT routes R004 (44.2% on time) and R001 (44.3%) have the lowest on-time rates.
  - Their problem is **early** running as well as late: 30.1% of R004 arrivals and 24.2% of R001 arrivals are at least 2 min early.
- **Biggest delay pattern (peak congestion):**
  - 117 of 118 routes are slower in *both* weekday peaks than at midday.
  - Across the system, mean arrival delay is 6.71 min in the evening peak and 5.54 min in the morning peak, against 1.70 min at midday.
  - Delay builds up along the route: R039's evening trips add 11.6 min between the first and last stop.
- **Worst bottleneck stop:** Shalimar Block 5 (S0318), where 14.5% of the trips serving it log a congestion delay, mostly traffic congestion. It is followed by DHA Mor (S0105, 13.3%, junction bottleneck).
  - Railway Station (S0001) is the largest bottleneck by volume: 30,277 congestion records across the 12 routes that serve it.
- **Consistently delayed:**
  - 30 routes are later than the system average on at least 75% of their days; R029 is later on every one of its 365 days.
  - 177 vehicles also qualify. Seven vehicles in the V07xx range averaged a daily late share above 99%.
- **Schedule adherence (weekdays):**
  - 49.1% of arrivals are on time, 40.1% late and 10.9% early.
  - 16,891 of 1,553,542 scheduled trips were cancelled.
  - Only 0.82% of intervals are irregular (bunched or gapped).
- **Bunching** is rare: 0.29% of assessed headways are bunched, with 146 overtakings in the year.

## Service planning

- **Frequency vs demand** (route × direction × day class × period cells):
  - 2,691 cells are well matched.
  - 306 have too little service, led by R107 and R097 weekday peaks with average occupancy above 1.2.
  - 272 have too much service.
- **Capacity:**
  - 333 cells show excess demand. For 315 of them a larger vehicle type fits, for example standard buses instead of 30-seat minibuses on R097 and R107, or articulated buses on R024, R031 and R036. The other 18 need extra trips.
  - 2,119 cells show excess supply: 1,498 could use a smaller vehicle and 621 could run less often.
- **Underutilized:** 134 cells on 25 routes are underutilized and frequent enough to trim. Another 1,184 cells are equally empty but already infrequent, so they are reported but not recommended for cuts.
- **Route classes:**

| class | routes |
|---|---|
| Overcrowded | 77 |
| Reliable but Underutilized | 19 |
| Low Performing | 16 |
| Average | 3 |
| High Demand but Unreliable | 2 |
| Insufficient Data | 1 (R091, low passenger-count coverage) |

- **Composite scores:** the best is R073 (67.6), which is classed Overcrowded; the worst is R030 (22.3).

## Events and anomalies

- **Special events:** three city-wide spikes were detected from demand alone:

| date | routes spiking | max demand vs baseline |
|---|---|---|
| 2025-10-12 | 16 | 3.08× |
| 2026-03-01 | 14 | 2.35× |
| 2025-12-20 | 12 | 2.19× |

  - These dates also carry 238, 238 and 236 generator event trips respectively, which confirms the detection.
  - The detector only runs after enough history: 51 of the 135 route-days with event trips were flagged as spikes, and 44 more had too little same-day-type history to judge.
- **Anomalies:**
  - 35,719 duplicate-ticketing signals. Almost all are **overlapping journeys**: a card taps into a new journey a median of about 12 minutes before its previous journey ended.
  - 1,791 trips with abnormal travel time.
  - 250 trips with delays of at least 60 min.
  - 503 stop-days with irregular activity.
  - No impossible-occupancy or off-route tap signals remain after Phase 3 cleaning.

## Passengers (smart-card holders only)

This covers 56,779 registered card holders, not the whole population.

| segment | card holders | share of holders | share of estimated card journeys |
|---|---|---|---|
| Occasional | 39,545 | 69.6% | 61.6% |
| Long-distance | 10,507 | 18.5% | 14.7% |
| Peak-hour | 3,713 | 6.5% | 1.5% |
| Daily commuters | 2,282 | 4.0% | 22.2% |
| Weekend | 732 | 1.3% | 0.1% |

Daily commuters make up only 4.0% of card holders but account for 22.2% of their estimated journeys. Cash riders are not visible in any segment.
