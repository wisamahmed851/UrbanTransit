-- name: v_headway
-- kind: view
-- cache: true
-- item: 14
-- Actual headway (Phase 4: gap to the previous OPERATED trip, same route/day/direction)
-- versus the scheduled gap to that same previous operated trip. Ratios follow
-- config/thresholds.yaml bunching (< 0.5 bunched, > 1.5 service gap).
SELECT h.*,
       CASE WHEN h.scheduled_gap_min >= ${bunching_min_scheduled_headway_minutes}
            THEN h.headway_minutes / h.scheduled_gap_min END AS headway_ratio,
       CASE WHEN h.headway_minutes IS NULL OR h.scheduled_gap_min IS NULL
                 OR h.scheduled_gap_min < ${bunching_min_scheduled_headway_minutes} THEN NULL
            WHEN h.headway_minutes / h.scheduled_gap_min < ${bunching_headway_ratio_threshold} THEN 'bunched'
            WHEN h.headway_minutes / h.scheduled_gap_min > ${bunching_gap_ratio_threshold} THEN 'gap'
            ELSE 'regular' END AS headway_status
FROM (
  SELECT trip_id, route_id, direction, service_date, day_class, time_period, hour, headway_minutes, overtaking_flag,
         (unix_timestamp(scheduled_departure)
          - unix_timestamp(last(CASE WHEN actual_departure IS NOT NULL THEN scheduled_departure END, true)
              OVER (PARTITION BY route_id, service_date, direction ORDER BY scheduled_departure, trip_id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING))) / 60 AS scheduled_gap_min
  FROM v_trip
) h
