-- name: peak_stop_hours
-- kind: output
-- item: 4
-- Stop-specific peaks. The as-of indicator exists per route-hour, not per stop, so stop
-- peaks use the stop's own hourly tap-in profile: an hour is a peak when its expanded
-- boardings are >= zscore_threshold (thresholds.yaml) standard deviations above the stop's
-- mean hour. Only hours with observed taps enter the profile.
WITH d AS (
  SELECT day_class, count(DISTINCT service_date) AS days FROM v_trip GROUP BY day_class
), h AS (
  SELECT entry_stop_id AS stop_id, day_class, entry_hour AS hour, sum(expansion_factor) AS eb, count(*) AS card_taps
  FROM v_ticket GROUP BY entry_stop_id, day_class, entry_hour
), p AS (
  SELECT h.stop_id, h.day_class, h.hour, h.card_taps, h.eb / d.days AS est_boardings_per_day
  FROM h JOIN d ON h.day_class = d.day_class
), z AS (
  SELECT p.*,
         try_divide(est_boardings_per_day - avg(est_boardings_per_day) OVER (PARTITION BY stop_id, day_class),
                    stddev(est_boardings_per_day) OVER (PARTITION BY stop_id, day_class)) AS zscore
  FROM p
)
SELECT stop_id, day_class, hour, card_taps,
       round(est_boardings_per_day, 2) AS est_boardings_per_day,
       round(zscore, 3) AS zscore,
       coalesce(zscore >= ${peak_detection_zscore_threshold}, false) AS is_stop_peak_hour
FROM z
