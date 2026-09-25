-- name: eda_route_delay
-- kind: output
-- item: 1
-- Most / least delayed and most punctual routes. Only EVALUATED trips count (delay_minutes
-- NULL = cancelled or delay record quarantined); avg() skips them instead of treating them as 0.
SELECT v.route_id, r.route_code,
       count(*) AS trips,
       count(v.delay_minutes) AS evaluated_trips,
       round(avg(v.delay_minutes), 3) AS avg_delay_min,
       round(avg(CASE WHEN v.delay_minutes >= ${on_time_late_min} THEN 1.0
                      WHEN v.delay_minutes IS NOT NULL THEN 0.0 END), 4) AS late_share,
       round(avg(CAST(v.trip_punctuality AS DOUBLE)), 4) AS punctuality_rate,
       round(avg(v.arrival_delay_min), 3) AS avg_arrival_delay_min,
       rank() OVER (ORDER BY avg(v.delay_minutes) DESC) AS most_delayed_rank,
       rank() OVER (ORDER BY avg(CAST(v.trip_punctuality AS DOUBLE)) DESC) AS punctuality_rank
FROM v_trip v
JOIN routes r ON v.route_id = r.route_id
GROUP BY v.route_id, r.route_code
