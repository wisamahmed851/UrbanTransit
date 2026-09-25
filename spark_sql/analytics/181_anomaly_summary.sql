-- name: anomaly_summary
-- kind: output
-- item: 18
SELECT anomaly_type, entity_type, count(*) AS signals,
       count(DISTINCT entity_id) AS entities, count(DISTINCT service_date) AS dates
FROM anomalies
GROUP BY anomaly_type, entity_type
