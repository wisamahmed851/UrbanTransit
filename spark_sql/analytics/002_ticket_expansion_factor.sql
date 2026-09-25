-- name: ticket_expansion_factor
-- kind: both
-- item: 2
-- Expansion factor = counted boardings / card tickets, per route x month x time period
-- (CMD-010 decision). Numerator and denominator use the SAME measured trips, so trips
-- without passenger counts neither inflate nor deflate the factor. Sparse cells fall
-- back to route x month, then system x month.
WITH taps AS (
  SELECT trip_id, count(*) AS card_tickets FROM tickets GROUP BY trip_id
), cell AS (
  SELECT v.route_id, v.year_month, v.time_period,
         sum(v.boardings) AS counted_boardings,
         sum(CASE WHEN v.boardings IS NOT NULL THEN coalesce(k.card_tickets, 0) END) AS card_tickets
  FROM v_trip v LEFT JOIN taps k ON v.trip_id = k.trip_id
  GROUP BY v.route_id, v.year_month, v.time_period
), rm AS (
  SELECT route_id, year_month, sum(counted_boardings) AS b, sum(card_tickets) AS n FROM cell GROUP BY route_id, year_month
), sm AS (
  SELECT year_month, sum(counted_boardings) AS b, sum(card_tickets) AS n FROM cell GROUP BY year_month
)
SELECT c.route_id, c.year_month, c.time_period, c.counted_boardings, c.card_tickets,
       CASE WHEN c.card_tickets >= ${expansion_min_tickets_per_cell} THEN try_divide(c.counted_boardings, c.card_tickets)
            WHEN rm.n >= ${expansion_min_tickets_per_cell} THEN try_divide(rm.b, rm.n)
            ELSE try_divide(sm.b, sm.n) END AS expansion_factor,
       CASE WHEN c.card_tickets >= ${expansion_min_tickets_per_cell} THEN 'route_month_period'
            WHEN rm.n >= ${expansion_min_tickets_per_cell} THEN 'route_month'
            ELSE 'system_month' END AS factor_level
FROM cell c
JOIN rm ON c.route_id = rm.route_id AND c.year_month = rm.year_month
JOIN sm ON c.year_month = sm.year_month
