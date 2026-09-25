SELECT tr.trip_id, pc.boardings, pc.alightings, pc.max_load
FROM trips tr LEFT JOIN passenger_counts pc ON tr.trip_id = pc.trip_id
