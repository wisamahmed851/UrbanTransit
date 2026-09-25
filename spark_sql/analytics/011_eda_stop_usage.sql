-- name: eda_stop_usage
-- kind: output
-- item: 1
-- Busiest / least-used stops from smart-card taps x expansion factor. Per-day rates use the
-- days the stop was open (stops opened mid-year are not diluted by days before opening).
-- A stop with no card taps shows 0 observed taps (a real observation, not missing data).
WITH b AS (
  SELECT entry_stop_id AS stop_id, count(*) AS card_boardings, sum(expansion_factor) AS est_boardings
  FROM v_ticket GROUP BY entry_stop_id
), a AS (
  SELECT exit_stop_id AS stop_id, count(*) AS card_alightings, sum(expansion_factor) AS est_alightings
  FROM v_ticket GROUP BY exit_stop_id
), span AS (
  SELECT min(service_date) AS first_day, max(service_date) AS last_day FROM v_trip
), s AS (
  SELECT st.stop_id, st.stop_name, st.zone, st.stop_type, st.opened_date,
         datediff(span.last_day, greatest(coalesce(st.opened_date, span.first_day), span.first_day)) + 1 AS days_open
  FROM stops st CROSS JOIN span
)
SELECT s.stop_id, s.stop_name, s.zone, s.stop_type, s.days_open,
       coalesce(b.card_boardings, 0) AS card_boardings,
       coalesce(a.card_alightings, 0) AS card_alightings,
       round(coalesce(b.est_boardings, 0) / s.days_open, 1) AS est_boardings_per_day,
       round(coalesce(a.est_alightings, 0) / s.days_open, 1) AS est_alightings_per_day,
       round((coalesce(b.est_boardings, 0) + coalesce(a.est_alightings, 0)) / s.days_open, 1) AS est_turnover_per_day,
       dense_rank() OVER (ORDER BY (coalesce(b.est_boardings, 0) + coalesce(a.est_alightings, 0)) / s.days_open DESC) AS usage_rank
FROM s
LEFT JOIN b ON s.stop_id = b.stop_id
LEFT JOIN a ON s.stop_id = a.stop_id
