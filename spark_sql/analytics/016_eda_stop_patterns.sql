-- name: eda_stop_patterns
-- kind: output
-- item: 1
-- Stop-level boarding / alighting pattern by day class and time period (boardings by tap-in
-- time, alightings by tap-out time), expanded from card taps, per day of that day class.
WITH days AS (
  SELECT day_class, count(DISTINCT service_date) AS days FROM v_trip GROUP BY day_class
), b AS (
  SELECT entry_stop_id AS stop_id, day_class, entry_time_period AS time_period, sum(expansion_factor) AS eb
  FROM v_ticket GROUP BY entry_stop_id, day_class, entry_time_period
), a AS (
  SELECT exit_stop_id AS stop_id, day_class, exit_time_period AS time_period, sum(expansion_factor) AS ea
  FROM v_ticket GROUP BY exit_stop_id, day_class, exit_time_period
), j AS (
  SELECT coalesce(b.stop_id, a.stop_id) AS stop_id, coalesce(b.day_class, a.day_class) AS day_class,
         coalesce(b.time_period, a.time_period) AS time_period,
         coalesce(b.eb, 0) AS eb, coalesce(a.ea, 0) AS ea
  FROM b FULL OUTER JOIN a
    ON b.stop_id = a.stop_id AND b.day_class = a.day_class AND b.time_period = a.time_period
)
SELECT j.stop_id, j.day_class, j.time_period,
       round(j.eb / d.days, 2) AS est_boardings_per_day,
       round(j.ea / d.days, 2) AS est_alightings_per_day,
       round((j.eb - j.ea) / d.days, 2) AS net_boardings_per_day,
       CASE WHEN j.eb >= 1.5 * j.ea THEN 'origin_dominant'
            WHEN j.ea >= 1.5 * j.eb THEN 'destination_dominant'
            ELSE 'balanced' END AS pattern
FROM j JOIN days d ON j.day_class = d.day_class
