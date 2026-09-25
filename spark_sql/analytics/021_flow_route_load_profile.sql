-- name: flow_route_load_profile
-- kind: output
-- item: 2
-- Boarding / alighting pattern along each route and direction: expanded boardings and
-- alightings per stop and the implied on-board load after the stop (running sum).
WITH b AS (
  SELECT route_id, direction, entry_stop_id AS stop_id, sum(expansion_factor) AS eb
  FROM v_ticket GROUP BY route_id, direction, entry_stop_id
), a AS (
  SELECT route_id, direction, exit_stop_id AS stop_id, sum(expansion_factor) AS ea
  FROM v_ticket GROUP BY route_id, direction, exit_stop_id
), d AS (
  SELECT route_id, count(DISTINCT service_date) AS days FROM v_trip GROUP BY route_id
)
SELECT rs.route_id, rs.direction, rs.stop_sequence, rs.stop_id, rs.distance_from_start_km,
       round(coalesce(b.eb, 0) / d.days, 2) AS est_boardings_per_day,
       round(coalesce(a.ea, 0) / d.days, 2) AS est_alightings_per_day,
       round(sum(coalesce(b.eb, 0) - coalesce(a.ea, 0)) OVER (
               PARTITION BY rs.route_id, rs.direction ORDER BY rs.stop_sequence
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) / d.days, 2) AS est_onboard_after_stop_per_day
FROM route_stops rs
JOIN d ON rs.route_id = d.route_id
LEFT JOIN b ON rs.route_id = b.route_id AND rs.direction = b.direction AND rs.stop_id = b.stop_id
LEFT JOIN a ON rs.route_id = a.route_id AND rs.direction = a.direction AND rs.stop_id = a.stop_id
