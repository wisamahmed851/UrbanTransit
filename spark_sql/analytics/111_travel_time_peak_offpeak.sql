-- name: travel_time_peak_offpeak
-- kind: output
-- item: 11
-- Weekday peak (morning + evening peak periods) vs off-peak travel time per route/direction.
SELECT route_id, direction,
       count(CASE WHEN time_period IN ('morning_peak', 'evening_peak') THEN travel_time_min END) AS peak_trips,
       count(CASE WHEN time_period NOT IN ('morning_peak', 'evening_peak') THEN travel_time_min END) AS offpeak_trips,
       round(avg(CASE WHEN time_period IN ('morning_peak', 'evening_peak') THEN travel_time_min END), 2) AS peak_actual_min,
       round(avg(CASE WHEN time_period NOT IN ('morning_peak', 'evening_peak') THEN travel_time_min END), 2) AS offpeak_actual_min,
       round(avg(CASE WHEN time_period IN ('morning_peak', 'evening_peak') THEN scheduled_runtime_min END), 2) AS peak_scheduled_min,
       round(avg(CASE WHEN time_period NOT IN ('morning_peak', 'evening_peak') THEN scheduled_runtime_min END), 2) AS offpeak_scheduled_min,
       round(avg(CASE WHEN time_period IN ('morning_peak', 'evening_peak') THEN travel_time_min END)
             - avg(CASE WHEN time_period NOT IN ('morning_peak', 'evening_peak') THEN travel_time_min END), 2) AS peak_minus_offpeak_min,
       round(try_divide(avg(CASE WHEN time_period IN ('morning_peak', 'evening_peak') THEN travel_time_min END),
                        avg(CASE WHEN time_period NOT IN ('morning_peak', 'evening_peak') THEN travel_time_min END)) - 1, 4) AS peak_penalty_pct
FROM v_trip
WHERE day_class = 'weekday' AND travel_time_min IS NOT NULL
GROUP BY route_id, direction
