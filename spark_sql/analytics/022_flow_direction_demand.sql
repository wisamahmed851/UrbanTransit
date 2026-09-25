-- name: flow_direction_demand
-- kind: output
-- item: 2
-- Direction-wise demand from passenger counters (all riders, not just card holders).
-- direction_share is NULL when a cell has no measured trip (unknown, not zero).
WITH c AS (
  SELECT route_id, direction, day_class, time_period,
         count(DISTINCT service_date) AS days,
         sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated_trips,
         count(boardings) AS measured_trips,
         avg(boardings) AS avg_boardings
  FROM v_trip GROUP BY route_id, direction, day_class, time_period
), e AS (
  SELECT c.*, avg_boardings * operated_trips / days AS est_boardings_per_day FROM c
), s AS (
  SELECT e.*, try_divide(est_boardings_per_day,
                         sum(est_boardings_per_day) OVER (PARTITION BY route_id, day_class, time_period)) AS direction_share
  FROM e
)
SELECT route_id, direction, day_class, time_period, days, operated_trips, measured_trips,
       round(avg_boardings, 2) AS avg_boardings_per_trip,
       round(est_boardings_per_day, 1) AS est_boardings_per_day,
       round(direction_share, 4) AS direction_share,
       CASE WHEN direction_share IS NULL THEN NULL
            WHEN direction_share >= 0.65 THEN 'dominant'
            WHEN direction_share <= 0.35 THEN 'minor'
            ELSE 'balanced' END AS direction_balance
FROM s
