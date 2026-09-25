-- name: delay_accumulation
-- kind: output
-- item: 9
-- Delay accumulated along the route = arrival delay at the last stop minus departure
-- deviation at the first stop (completed trips), per route, direction and time period.
SELECT route_id, direction, time_period,
       count(arrival_delay_min) AS completed_trips,
       max(distance_km) AS distance_km,
       round(avg(schedule_deviation_min), 3) AS avg_departure_deviation_min,
       round(avg(arrival_delay_min), 3) AS avg_arrival_delay_min,
       round(avg(arrival_delay_min - schedule_deviation_min), 3) AS avg_accumulated_delay_min,
       round(try_divide(avg(arrival_delay_min - schedule_deviation_min), max(distance_km)), 4) AS accumulated_delay_per_km
FROM v_trip
WHERE arrival_delay_min IS NOT NULL
GROUP BY route_id, direction, time_period
