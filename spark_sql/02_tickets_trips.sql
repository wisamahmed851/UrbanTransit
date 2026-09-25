SELECT t.*, tr.vehicle_id AS trip_vehicle_id, tr.scheduled_departure, tr.actual_departure
FROM tickets t LEFT JOIN trips tr ON t.trip_id = tr.trip_id
