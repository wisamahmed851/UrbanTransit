-- name: holidays
-- kind: view
-- item: 0
-- Public holidays = dates "added" to the HOL (holiday) service calendar.
SELECT `date` AS service_date, max(reason) AS holiday_name
FROM (SELECT inline(exceptions) FROM service_calendar WHERE service_id = 'HOL') x
WHERE exception_type = 'added'
GROUP BY `date`
