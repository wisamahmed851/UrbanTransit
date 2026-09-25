-- name: passenger_segments
-- kind: output
-- item: 19
-- partitions: 2
-- Registered smart-card holders only (tickets are a ~3-4% sample of riders; cash riders are
-- invisible here). Rules are applied in this order, first match wins:
--   Daily Commuter          >= 3 active days per week of their active span and >= 80% weekday journeys
--   Weekend Traveller       >= 50% of journeys on weekends
--   Long-Distance Traveller average journey km >= 80th percentile of all card holders
--   Peak-Hour Traveller     >= 70% of journeys tapped in during morning/evening peak periods
--   Occasional Traveller    everyone else
-- DQ15 tickets (passenger not registered) cannot be attributed to a person and are excluded.
WITH j AS (
  SELECT * FROM v_ticket WHERE passenger_id IS NOT NULL AND NOT array_contains(dq_flags, 'DQ15')
), p AS (
  SELECT passenger_id,
         count(*) AS journeys,
         count(DISTINCT service_date) AS active_days,
         greatest(1.0, (datediff(max(service_date), min(service_date)) + 1) / 7.0) AS active_span_weeks,
         avg(CASE WHEN day_class = 'weekday' THEN 1.0 ELSE 0.0 END) AS weekday_share,
         avg(CASE WHEN day_class = 'weekend' THEN 1.0 ELSE 0.0 END) AS weekend_share,
         avg(CASE WHEN entry_time_period IN ('morning_peak', 'evening_peak') THEN 1.0 ELSE 0.0 END) AS peak_share,
         avg(journey_km) AS avg_journey_km,
         sum(expansion_factor) AS est_journeys_represented
  FROM j GROUP BY passenger_id
), q AS (
  SELECT percentile_approx(avg_journey_km, ${segmentation_long_distance_percentile}) AS long_km FROM p
)
SELECT p.passenger_id, pa.passenger_type, pa.age_group, p.journeys, p.active_days,
       round(p.active_span_weeks, 2) AS active_span_weeks,
       round(p.active_days / p.active_span_weeks, 3) AS active_days_per_week,
       round(p.weekday_share, 4) AS weekday_share, round(p.weekend_share, 4) AS weekend_share,
       round(p.peak_share, 4) AS peak_share, round(p.avg_journey_km, 2) AS avg_journey_km,
       round(q.long_km, 2) AS long_distance_threshold_km,
       round(p.est_journeys_represented, 1) AS est_journeys_represented,
       CASE WHEN p.active_days / p.active_span_weeks >= ${segmentation_commuter_min_days_per_week}
                 AND p.weekday_share >= ${segmentation_commuter_min_weekday_share} THEN 'Daily Commuter'
            WHEN p.weekend_share >= ${segmentation_weekend_min_share} THEN 'Weekend Traveller'
            WHEN p.avg_journey_km >= q.long_km THEN 'Long-Distance Traveller'
            WHEN p.peak_share >= ${segmentation_peak_min_share} THEN 'Peak-Hour Traveller'
            ELSE 'Occasional Traveller' END AS segment
FROM p CROSS JOIN q
LEFT JOIN passengers pa ON p.passenger_id = pa.passenger_id
