-- name: peak_period_summary
-- kind: output
-- item: 4
-- Morning peak / midday / evening peak / weekend / holiday from actual demand. A period is
-- "peak" when >= 50% of its trips carry the LEAK-FREE peak_hour_indicator_asof flag.
WITH d AS (
  SELECT day_class, count(DISTINCT service_date) AS days FROM v_trip GROUP BY day_class
), c AS (
  SELECT day_class, time_period, count(*) AS trips,
         sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated_trips,
         count(boardings) AS measured_trips,
         avg(boardings) AS avg_boardings,
         avg(occupancy_pct) AS avg_occupancy,
         count(peak_hour_indicator_asof) AS asof_trips,
         avg(CAST(peak_hour_indicator_asof AS DOUBLE)) AS peak_rate_asof
  FROM v_trip GROUP BY day_class, time_period
), e AS (
  SELECT c.*, d.days, c.avg_boardings * c.operated_trips / d.days AS est_boardings_per_day
  FROM c JOIN d ON c.day_class = d.day_class
)
SELECT day_class, time_period, days, trips, measured_trips, asof_trips,
       round(avg_boardings, 2) AS avg_boardings_per_trip,
       round(est_boardings_per_day, 1) AS est_boardings_per_day,
       round(try_divide(est_boardings_per_day, sum(est_boardings_per_day) OVER (PARTITION BY day_class)), 4) AS share_of_day,
       round(avg_occupancy, 4) AS avg_occupancy,
       round(peak_rate_asof, 4) AS peak_rate_asof,
       peak_rate_asof >= ${peak_asof_peak_rate} AS is_peak_period
FROM e
