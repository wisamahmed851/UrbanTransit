-- name: travel_time_analysis
-- kind: output
-- item: 11
-- Scheduled vs actual travel time per route, direction, day class and period, and the
-- deviation from the route-direction's historical (whole-year, trip-weighted) average.
WITH c AS (
  SELECT route_id, direction, day_class, time_period,
         count(travel_time_min) AS completed_trips,
         avg(scheduled_runtime_min) AS scheduled_min,
         avg(travel_time_min) AS actual_min,
         stddev(travel_time_min) AS std_min,
         sum(travel_time_min) AS sum_actual
  FROM v_trip WHERE travel_time_min IS NOT NULL
  GROUP BY route_id, direction, day_class, time_period
), h AS (
  SELECT c.*, sum(sum_actual) OVER (PARTITION BY route_id, direction)
              / sum(completed_trips) OVER (PARTITION BY route_id, direction) AS historical_avg_min
  FROM c
)
SELECT route_id, direction, day_class, time_period, completed_trips,
       round(scheduled_min, 2) AS scheduled_min, round(actual_min, 2) AS actual_min,
       round(actual_min - scheduled_min, 2) AS excess_min,
       round(try_divide(actual_min, scheduled_min), 4) AS actual_to_scheduled,
       round(std_min, 2) AS std_min,
       round(historical_avg_min, 2) AS historical_avg_min,
       round(actual_min - historical_avg_min, 2) AS vs_historical_min
FROM h
