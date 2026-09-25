SELECT tr.trip_id, d.delay_minutes, d.delay_reason
FROM trips tr LEFT JOIN delays d ON tr.trip_id = d.trip_id
 