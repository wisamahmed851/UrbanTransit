-- name: anomalies
-- kind: output
-- item: 18
-- One long table of anomaly signals (anomaly_type, entity, date, observed vs expected):
--   demand_spike / demand_drop   route-day vs robust same-weekday baseline (special_event_route_days)
--   abnormal_delay               recorded trip delay >= 60 min
--   impossible_occupancy         max_load > boardings, or denied boardings on a bus under half full
--   abnormal_travel_time         actual / scheduled runtime < 0.5 or > 2.0
--   unexpected_route_usage       card tap at a stop that is not on the trip's route
--   duplicate_ticketing_signal   same card taps in again at the SAME stop within 120 s, or taps
--                                in before its previous journey ended (after Phase 3 removed
--                                exact duplicates). A quick tap at a different stop is a normal
--                                transfer and is not flagged.
--   irregular_stop_activity      stop-day card taps >= 3x or <= 0.2x the stop's same-weekday median
WITH demand AS (
  SELECT CASE day_status WHEN 'spike' THEN 'demand_spike' ELSE 'demand_drop' END AS anomaly_type,
         'route' AS entity_type, route_id AS entity_id, service_date,
         CAST(observed_demand AS DOUBLE) AS observed_value, CAST(baseline_demand AS DOUBLE) AS expected_value,
         concat('ratio=', demand_ratio, CASE WHEN is_holiday THEN concat(' holiday=', holiday_name) ELSE '' END) AS detail
  FROM special_event_route_days WHERE day_status IN ('spike', 'drop')
), delay AS (
  SELECT 'abnormal_delay', 'trip', trip_id, service_date, CAST(round(delay_minutes, 2) AS DOUBLE), CAST(NULL AS DOUBLE),
         concat('route=', route_id, ' severity=', delay_severity)
  FROM v_trip WHERE delay_minutes >= ${anomalies_abnormal_delay_min}
), occ AS (
  SELECT 'impossible_occupancy', 'trip', trip_id, service_date, CAST(max_load AS DOUBLE), CAST(boardings AS DOUBLE),
         concat('route=', route_id, ' max_load > boardings')
  FROM v_trip WHERE max_load > boardings
  UNION ALL
  SELECT 'impossible_occupancy', 'trip', trip_id, service_date, CAST(denied_boardings AS DOUBLE), CAST(round(occupancy_pct, 3) AS DOUBLE),
         concat('route=', route_id, ' denied boardings while under half full')
  FROM v_trip WHERE denied_boardings > 0 AND occupancy_pct < 0.5
), tt AS (
  SELECT 'abnormal_travel_time', 'trip', trip_id, service_date, CAST(round(travel_time_min, 1) AS DOUBLE),
         CAST(round(scheduled_runtime_min, 1) AS DOUBLE),
         concat('route=', route_id, ' ratio=', round(try_divide(travel_time_min, scheduled_runtime_min), 2))
  FROM v_trip
  WHERE try_divide(travel_time_min, scheduled_runtime_min) < ${anomalies_travel_time_low_ratio}
     OR try_divide(travel_time_min, scheduled_runtime_min) > ${anomalies_travel_time_high_ratio}
), rs AS (
  SELECT DISTINCT route_id, stop_id FROM route_stops
), usage AS (
  SELECT 'unexpected_route_usage', 'ticket', k.ticket_id, k.service_date, CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE),
         concat('route=', k.route_id, CASE WHEN a.stop_id IS NULL THEN concat(' entry ', k.entry_stop_id, ' not on route') ELSE '' END,
                CASE WHEN b.stop_id IS NULL THEN concat(' exit ', k.exit_stop_id, ' not on route') ELSE '' END)
  FROM v_ticket k
  LEFT JOIN rs a ON k.route_id = a.route_id AND k.entry_stop_id = a.stop_id
  LEFT JOIN rs b ON k.route_id = b.route_id AND k.exit_stop_id = b.stop_id
  WHERE a.stop_id IS NULL OR b.stop_id IS NULL
), taps AS (
  SELECT passenger_id, service_date, ticket_id, entry_time, entry_stop_id,
         lag(ticket_id) OVER w AS prev_ticket, lag(entry_time) OVER w AS prev_entry, lag(exit_time) OVER w AS prev_exit,
         lag(entry_stop_id) OVER w AS prev_entry_stop
  FROM v_ticket WHERE passenger_id IS NOT NULL
  WINDOW w AS (PARTITION BY passenger_id ORDER BY entry_time, ticket_id)
), dup AS (
  SELECT 'duplicate_ticketing_signal', 'passenger', passenger_id, service_date,
         CAST(unix_timestamp(entry_time) - unix_timestamp(prev_entry) AS DOUBLE), CAST(NULL AS DOUBLE),
         concat('ticket=', ticket_id, ' previous=', prev_ticket,
                CASE WHEN entry_time < prev_exit THEN ' overlaps previous journey' ELSE ' repeat tap' END)
  FROM taps
  WHERE prev_entry IS NOT NULL
    AND ((unix_timestamp(entry_time) - unix_timestamp(prev_entry) <= ${anomalies_duplicate_tap_seconds}
          AND entry_stop_id = prev_entry_stop)
         OR entry_time < prev_exit)
), sd AS (
  SELECT stop_id, service_date, boarding_count, dayofweek(service_date) AS dow,
         datediff(service_date, DATE'2000-01-01') AS day_idx
  FROM stop_daily_demand
), sb AS (
  SELECT sd.*, array_sort(collect_list(boarding_count) OVER (
           PARTITION BY stop_id, dow ORDER BY day_idx RANGE BETWEEN ${events_baseline_days} PRECEDING AND 7 PRECEDING)) AS hist
  FROM sd
), sm AS (
  SELECT stop_id, service_date, boarding_count,
         CASE WHEN size(hist) >= ${events_min_baseline_days} THEN element_at(hist, CAST((size(hist) + 1) div 2 AS INT)) END AS baseline
  FROM sb
), stop AS (
  SELECT 'irregular_stop_activity', 'stop', stop_id, service_date, CAST(boarding_count AS DOUBLE), CAST(baseline AS DOUBLE),
         concat('card taps vs same-weekday median, ratio=', round(boarding_count / baseline, 2))
  FROM sm
  WHERE baseline >= ${anomalies_stop_min_baseline}
    AND (boarding_count >= ${anomalies_stop_spike_ratio} * baseline OR boarding_count <= ${anomalies_stop_drop_ratio} * baseline)
)
SELECT * FROM demand
UNION ALL SELECT * FROM delay
UNION ALL SELECT * FROM occ
UNION ALL SELECT * FROM tt
UNION ALL SELECT * FROM usage
UNION ALL SELECT * FROM dup
UNION ALL SELECT * FROM stop
