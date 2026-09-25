-- name: delay_by_stop
-- kind: output
-- item: 9
-- Stop-level delay and bottleneck detection from the delay EXCEPTION log (records exist only
-- where a trip was >= 5 min late at a timing point, see feature_catalog.md). Counts are
-- normalised by exposure = operated trips on every route/direction that serves the stop.
-- Bottleneck = top 5% of stops by congestion-record rate (junction_bottleneck,
-- traffic_congestion, passenger_boarding) with >= 50 records.
WITH dl AS (
  SELECT d.stop_id, d.trip_id, d.delay_minutes, d.delay_reason
  FROM delays d JOIN v_trip v ON d.trip_id = v.trip_id
  WHERE d.delay_reason <> 'early_running'
), rec AS (
  SELECT stop_id, count(*) AS late_records,
         avg(delay_minutes) AS avg_record_delay_min,
         sum(CASE WHEN delay_reason IN ('junction_bottleneck', 'traffic_congestion', 'passenger_boarding') THEN 1 ELSE 0 END) AS congestion_records,
         mode(delay_reason) AS top_reason
  FROM dl GROUP BY stop_id
), ops AS (
  SELECT route_id, direction, sum(CASE WHEN trip_status = 'completed' THEN 1 ELSE 0 END) AS operated
  FROM v_trip GROUP BY route_id, direction
), exposure AS (
  SELECT rs.stop_id, sum(o.operated) AS trips_serving, count(DISTINCT rs.route_id) AS routes_serving
  FROM (SELECT DISTINCT route_id, direction, stop_id FROM route_stops) rs
  JOIN ops o ON rs.route_id = o.route_id AND rs.direction = o.direction
  GROUP BY rs.stop_id
), j AS (
  SELECT s.stop_id, s.stop_name, s.zone, s.stop_type, e.routes_serving, e.trips_serving,
         coalesce(r.late_records, 0) AS late_records,
         coalesce(r.congestion_records, 0) AS congestion_records,
         r.avg_record_delay_min, r.top_reason,
         try_divide(coalesce(r.late_records, 0), e.trips_serving) AS late_record_rate,
         try_divide(coalesce(r.congestion_records, 0), e.trips_serving) AS congestion_record_rate
  FROM stops s
  JOIN exposure e ON s.stop_id = e.stop_id
  LEFT JOIN rec r ON s.stop_id = r.stop_id
)
SELECT stop_id, stop_name, zone, stop_type, routes_serving, trips_serving, late_records, congestion_records,
       round(avg_record_delay_min, 2) AS avg_record_delay_min, top_reason,
       round(late_record_rate, 5) AS late_record_rate,
       round(congestion_record_rate, 5) AS congestion_record_rate,
       round(percent_rank() OVER (ORDER BY congestion_record_rate), 4) AS congestion_rate_pctile,
       (percent_rank() OVER (ORDER BY congestion_record_rate) >= 1 - ${delay_bottleneck_top_share}
        AND congestion_records >= ${delay_bottleneck_min_records}) AS is_bottleneck
FROM j
