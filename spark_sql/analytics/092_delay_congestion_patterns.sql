-- name: delay_congestion_patterns
-- kind: output
-- item: 9
-- Morning / evening congestion pattern per route on weekdays: mean arrival delay in each peak
-- versus midday. arrival_delay_min is used (all completed trips) because the exception-based
-- delay_minutes is 0 inside the tolerance band and would hide small peak effects.
WITH p AS (
  SELECT route_id, time_period, avg(arrival_delay_min) AS a
  FROM v_trip WHERE day_class = 'weekday' GROUP BY route_id, time_period
), w AS (
  SELECT route_id,
         max(CASE WHEN time_period = 'early_morning' THEN a END) AS early_morning_delay,
         max(CASE WHEN time_period = 'morning_peak' THEN a END) AS morning_peak_delay,
         max(CASE WHEN time_period = 'midday' THEN a END) AS midday_delay,
         max(CASE WHEN time_period = 'evening_peak' THEN a END) AS evening_peak_delay,
         max(CASE WHEN time_period = 'evening' THEN a END) AS evening_delay
  FROM p GROUP BY route_id
)
SELECT route_id,
       round(early_morning_delay, 3) AS early_morning_delay, round(morning_peak_delay, 3) AS morning_peak_delay,
       round(midday_delay, 3) AS midday_delay, round(evening_peak_delay, 3) AS evening_peak_delay,
       round(evening_delay, 3) AS evening_delay,
       round(morning_peak_delay - midday_delay, 3) AS morning_excess_min,
       round(evening_peak_delay - midday_delay, 3) AS evening_excess_min,
       CASE WHEN morning_peak_delay - midday_delay >= ${delay_congestion_extra_min}
                 AND evening_peak_delay - midday_delay >= ${delay_congestion_extra_min} THEN 'both_peaks'
            WHEN morning_peak_delay - midday_delay >= ${delay_congestion_extra_min} THEN 'morning_congestion'
            WHEN evening_peak_delay - midday_delay >= ${delay_congestion_extra_min} THEN 'evening_congestion'
            ELSE 'no_peak_pattern' END AS congestion_pattern
FROM w
