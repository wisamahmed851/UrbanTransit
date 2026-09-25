-- name: eda_travel_time_variation
-- kind: output
-- item: 1
-- Route-wise travel-time variation (completed trips only; cancelled trips have no travel time).
SELECT route_id, direction,
       count(travel_time_min) AS completed_trips,
       round(avg(travel_time_min), 2) AS avg_travel_min,
       round(stddev(travel_time_min), 2) AS std_travel_min,
       round(try_divide(stddev(travel_time_min), avg(travel_time_min)), 4) AS cv_travel_time,
       round(percentile_approx(travel_time_min, 0.1), 2) AS p10_travel_min,
       round(percentile_approx(travel_time_min, 0.9), 2) AS p90_travel_min,
       round(avg(scheduled_runtime_min), 2) AS avg_scheduled_min,
       round(try_divide(avg(travel_time_min), avg(scheduled_runtime_min)), 4) AS actual_to_scheduled,
       rank() OVER (ORDER BY try_divide(stddev(travel_time_min), avg(travel_time_min)) DESC) AS variation_rank
FROM v_trip
GROUP BY route_id, direction
