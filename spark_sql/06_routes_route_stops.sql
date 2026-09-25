SELECT r.route_id, rs.stop_id, rs.direction, rs.stop_sequence
FROM routes r LEFT JOIN route_stops rs ON r.route_id = rs.route_id
