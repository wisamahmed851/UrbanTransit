-- name: headway_bunching
-- kind: output
-- item: 14
-- Headway regularity and bunching per route, direction and period. Bunched = actual headway
-- < 0.5 x scheduled gap; gap = > 1.5 x (thresholds.yaml). Overtakings are negative headways
-- (a bus left before the one scheduled ahead of it).
SELECT route_id, direction, time_period,
       count(headway_minutes) AS headways,
       count(headway_status) AS headways_assessed,
       round(avg(headway_minutes), 2) AS avg_headway_min,
       round(avg(scheduled_gap_min), 2) AS avg_scheduled_gap_min,
       round(try_divide(stddev(headway_minutes), avg(headway_minutes)), 4) AS headway_cv,
       sum(CASE WHEN headway_status = 'bunched' THEN 1 ELSE 0 END) AS bunched,
       sum(CASE WHEN headway_status = 'gap' THEN 1 ELSE 0 END) AS gaps,
       sum(CASE WHEN overtaking_flag THEN 1 ELSE 0 END) AS overtakings,
       round(try_divide(sum(CASE WHEN headway_status = 'bunched' THEN 1 ELSE 0 END), count(headway_status)), 4) AS bunched_share,
       round(try_divide(sum(CASE WHEN headway_status = 'gap' THEN 1 ELSE 0 END), count(headway_status)), 4) AS gap_share
FROM v_headway
GROUP BY route_id, direction, time_period
