-- name: flow_od_pairs
-- kind: output
-- item: 2
-- Origin-destination flows (stop to stop, all routes). card_journeys = observed smart-card
-- sample; est_journeys = card journeys x route/month/period expansion factor.
WITH n AS (SELECT count(DISTINCT service_date) AS days FROM v_trip)
SELECT k.entry_stop_id AS origin_stop_id, k.exit_stop_id AS destination_stop_id,
       count(*) AS card_journeys,
       round(sum(k.expansion_factor), 1) AS est_journeys,
       round(sum(k.expansion_factor) / max(n.days), 2) AS est_journeys_per_day,
       round(avg(k.journey_km), 2) AS avg_journey_km,
       round(avg(k.ride_min), 1) AS avg_ride_min,
       count(DISTINCT k.route_id) AS routes_used,
       dense_rank() OVER (ORDER BY sum(k.expansion_factor) DESC) AS flow_rank
FROM v_ticket k CROSS JOIN n
GROUP BY k.entry_stop_id, k.exit_stop_id
