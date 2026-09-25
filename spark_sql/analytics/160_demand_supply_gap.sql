-- name: demand_supply_gap
-- kind: output
-- item: 16
-- Demand vs supplied capacity at the peak load point, per route/direction/day class/period.
--   utilization     = sum(max_load) / sum(capacity) over counted trips with known capacity
--   excess_demand   : utilization >= 0.90 or >= 1 denied boarding per trip
--   excess_supply   : utilization < 0.30;  balanced otherwise
--   required_capacity = p90 max_load / 0.85 target load -> smallest vehicle type that fits.
--   Suggestion: larger_vehicle / smaller_vehicle / add_trips (no vehicle type is big enough)
--   / reduce_frequency / no_change. extra_trips_per_hour sizes add_trips with the largest type.
WITH vt AS (
  SELECT vehicle_type, max(capacity_total) AS capacity FROM vehicles
  WHERE capacity_total IS NOT NULL GROUP BY vehicle_type
), mx AS (
  SELECT max(capacity) AS max_capacity FROM vt
), c AS (
  SELECT route_id, direction, day_class, time_period,
         count(DISTINCT service_date) AS days,
         count(*) AS operated_trips,
         count(max_load) AS measured_trips,
         avg(capacity_total) AS avg_capacity,
         sum(CASE WHEN capacity_total IS NOT NULL THEN max_load END) AS sum_load,
         sum(CASE WHEN max_load IS NOT NULL THEN capacity_total END) AS sum_capacity,
         percentile_approx(max_load, 0.9) AS p90_load,
         avg(denied_boardings) AS denied_per_trip
  FROM v_trip WHERE trip_status = 'completed'
  GROUP BY route_id, direction, day_class, time_period
), g AS (
  SELECT c.*, operated_trips / (days * ${period_hours_case}) AS trips_per_hour,
         try_divide(sum_load, sum_capacity) AS utilization,
         p90_load / ${supply_target_load} AS required_capacity
  FROM c
), pick AS (
  SELECT g.route_id, g.direction, g.day_class, g.time_period,
         min_by(vt.vehicle_type, vt.capacity) AS suggested_vehicle_type, min(vt.capacity) AS suggested_capacity
  FROM g JOIN vt ON vt.capacity >= g.required_capacity
  GROUP BY g.route_id, g.direction, g.day_class, g.time_period
), s AS (
  SELECT g.*, pick.suggested_vehicle_type, pick.suggested_capacity, mx.max_capacity,
         CASE WHEN g.measured_trips < ${underutilized_min_measured_trips} OR g.utilization IS NULL THEN 'insufficient_data'
              WHEN g.utilization >= ${supply_excess_demand_utilization}
                   OR g.denied_per_trip >= ${supply_excess_demand_denied_per_trip} THEN 'excess_demand'
              WHEN g.utilization < ${supply_excess_supply_utilization} THEN 'excess_supply'
              ELSE 'balanced' END AS gap_status
  FROM g
  CROSS JOIN mx
  LEFT JOIN pick ON g.route_id = pick.route_id AND g.direction = pick.direction
                AND g.day_class = pick.day_class AND g.time_period = pick.time_period
)
SELECT route_id, direction, day_class, time_period, days, operated_trips, measured_trips,
       round(trips_per_hour, 2) AS trips_per_hour, round(avg_capacity, 1) AS avg_capacity,
       round(utilization, 4) AS utilization, p90_load, round(denied_per_trip, 3) AS denied_per_trip,
       round(required_capacity, 1) AS required_capacity, suggested_vehicle_type, suggested_capacity,
       gap_status,
       CASE WHEN gap_status = 'excess_demand' AND suggested_capacity IS NULL THEN 'add_trips'
            WHEN gap_status = 'excess_demand' AND suggested_capacity > avg_capacity THEN 'larger_vehicle'
            WHEN gap_status = 'excess_demand' THEN 'add_trips'
            WHEN gap_status = 'excess_supply' AND suggested_capacity < avg_capacity THEN 'smaller_vehicle'
            WHEN gap_status = 'excess_supply' THEN 'reduce_frequency'
            ELSE 'no_change' END AS suggestion,
       CASE WHEN gap_status = 'excess_demand' AND (suggested_capacity IS NULL OR suggested_capacity <= avg_capacity)
            THEN greatest(0, CAST(ceil(trips_per_hour * p90_load / (${supply_target_load} * max_capacity)) - trips_per_hour AS DOUBLE))
       END AS extra_trips_per_hour
FROM s
