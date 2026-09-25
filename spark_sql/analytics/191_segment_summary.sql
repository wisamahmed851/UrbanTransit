-- name: segment_summary
-- kind: output
-- item: 19
-- Segment sizes among card holders and the share of expanded journeys each represents.
-- Passenger counts are NOT expanded: the expansion factor scales journeys, not people.
SELECT segment,
       count(*) AS card_holders,
       round(count(*) / sum(count(*)) OVER (), 4) AS share_of_card_holders,
       round(avg(journeys), 1) AS avg_journeys,
       round(avg(active_days_per_week), 2) AS avg_active_days_per_week,
       round(avg(peak_share), 4) AS avg_peak_share,
       round(avg(avg_journey_km), 2) AS avg_journey_km,
       round(sum(est_journeys_represented) / sum(sum(est_journeys_represented)) OVER (), 4) AS share_of_est_journeys,
       mode(passenger_type) AS most_common_passenger_type
FROM passenger_segments
GROUP BY segment
