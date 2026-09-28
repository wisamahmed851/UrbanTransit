-- Run this once yourself (phpMyAdmin SQL tab, or `mysql -h127.0.0.1 -u urbantransit -p`).
-- Creates a SELECT-only MySQL user for Power BI so the dashboard can never
-- write to the database (SRS 1.8: no manually-created / editable dashboard values).
-- Change the password below before running.

CREATE USER IF NOT EXISTS 'powerbi_ro'@'%' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';
GRANT SELECT ON urbantransit_iq.* TO 'powerbi_ro'@'%';
FLUSH PRIVILEGES;

-- Verify:
-- SHOW GRANTS FOR 'powerbi_ro'@'%';
