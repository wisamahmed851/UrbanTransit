-- name: delay_stop_position_profile
-- kind: output
-- item: 9
-- Where along a route late records occur: stop position as a decile of the route/direction
-- stop sequence (0 = first stop, 9 = last), per route type and time period.
WITH mx AS (
  SELECT route_id, direction, max(stop_sequence) AS n FROM route_stops GROUP BY route_id, direction
), rs AS (
  SELECT route_id, direction, stop_id, min(stop_sequence) AS seq FROM route_stops GROUP BY route_id, direction, stop_id
), d AS (
  SELECT v.route_type, v.time_period, d.delay_minutes,
         least(9, CAST(floor(10 * (rs.seq - 1) / greatest(mx.n - 1, 1)) AS INT)) AS position_decile
  FROM delays d
  JOIN v_trip v ON d.trip_id = v.trip_id
  JOIN rs ON rs.route_id = v.route_id AND rs.direction = v.direction AND rs.stop_id = d.stop_id
  JOIN mx ON mx.route_id = v.route_id AND mx.direction = v.direction
  WHERE d.delay_reason <> 'early_running'
)
SELECT route_type, time_period, position_decile,
       count(*) AS late_records,
       round(avg(delay_minutes), 2) AS avg_delay_min
FROM d
GROUP BY route_type, time_period, position_decile
