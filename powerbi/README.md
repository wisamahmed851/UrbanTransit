# UrbanTransit IQ — Power BI Dashboard

Read-only visualization layer on top of the existing MySQL analytics tables
(`urbantransit_iq`, populated by `database/load_*.py`). Power BI never writes
to the database — it only queries what the pipeline already produced, per the
SRS's rule against manually-created dashboard values.

## 1. Install (one time)

1. **Power BI Desktop** — Microsoft Store → search "Power BI Desktop" → Install.
   (Also attempted via `winget install --id 9NTXR16HNW1T --source msstore` —
   check whether that finished; Store installs sometimes need you to accept a
   sign-in/terms prompt by hand the first time.)
2. **MySQL Connector/NET 8.0.x (x64)** — required by Power BI's built-in MySQL
   connector: https://dev.mysql.com/downloads/connector/net/
   - If Power BI still can't see the MySQL connector after installing this and
     restarting Power BI, install **MySQL Connector/ODBC 8.0 (x64)** instead
     (https://dev.mysql.com/downloads/connector/odbc/) and connect via
     Get Data → ODBC using a DSN pointing at `127.0.0.1:3306`.

No Power BI Pro / online license is needed. The deliverable is the local
`.pbix` file plus an exported PDF and screenshots.

## 2. Create a read-only database user

Your app's own credentials (`urbantransit` in `.env`) have full write access —
don't point Power BI at those. Run `powerbi/create_readonly_user.sql` once,
after changing the password inside it, either in phpMyAdmin's SQL tab or:

```
wsl mysql -h127.0.0.1 -u urbantransit -p < powerbi/create_readonly_user.sql
```

(MySQL runs inside WSL in this setup; port 3306 is forwarded to Windows, so
Power BI on Windows connects to `127.0.0.1:3306` normally.)

## 3. Connect Power BI to MySQL

1. Power BI Desktop → **Get Data → More → Database → MySQL database**.
2. Server: `127.0.0.1:3306`, Database: `urbantransit_iq`.
3. Data Connectivity mode: **Import** (tables are already small, pre-aggregated
   results — no need for DirectQuery).
4. Credentials: Database, username `powerbi_ro`, the password you set in step 2.
5. In the Navigator, **select only these tables** (leave everything else
   unchecked — `gps_events`, `users`, `roles`, `permissions`, `audit_log`,
   `job_runs` are either huge, raw, or not analytics data):

   - `routes`, `stops`, `vehicles`
   - `route_performance`, `route_reliability`, `route_clusters`
   - `eda_route_delay`, `eda_peak_hours`, `eda_peak_days`, `eda_stop_usage`
   - `delay_by_stop`, `delay_by_dimension`, `delay_congestion_patterns`, `delay_top_trips`
   - `overcrowding_summary`, `persistent_overcrowding`, `underutilized_services`
   - `demand_supply_gap`, `od_matrix`, `flow_direction_demand`, `flow_od_pairs`
   - `route_daily_boardings`
   - `travel_time_analysis`, `travel_time_peak_offpeak`, `schedule_adherence`
   - `headway_bunching`, `service_frequency`
   - `anomalies`, `anomaly_summary`, `special_event_dates`
   - `passenger_segments`, `segment_summary`, `peak_period_summary`
   - `pipeline_comparison`, `model_metrics`, `model_versions`, `python_cluster_profiles`, `cluster_profiles`
   - `recommendations`

6. Click **Transform Data** (not Load) so you can rename/clean columns first if
   needed, then **Close & Apply**.

## 4. Build the data model

In **Model view**:

- Relationships: `routes[route_id]` → one-to-many into every table above that
  has a `route_id` column (route_performance, eda_route_delay,
  overcrowding_summary, route_daily_boardings, route_clusters,
  recommendations, demand_supply_gap, service_frequency, etc.).
- `stops[stop_id]` → `delay_by_stop[stop_id]`, `eda_stop_usage[stop_id]`.
- `od_matrix`: make `origin_stop_id → stops[stop_id]` the active relationship;
  add a second relationship on `destination_stop_id` and mark it **inactive**
  (Power BI won't let two active paths to the same table). Use `USERELATIONSHIP`
  in DAX when you need the destination side.
- Add a date table: **Home → Enter Data** or `CALENDAR(MIN(...), MAX(...))` in a
  new calculated table, built off `route_daily_boardings[service_date]` (the
  only fact table with a real per-day date column — most others are already
  pre-aggregated summaries with no date column, so the date slicer will only
  filter demand/forecast visuals, not every page. Say this plainly if a
  reviewer asks why the date slicer doesn't affect the Delay page, etc.).

## 5. Add the measures

Create an empty table named **Measures** (Home → Enter Data, no columns, just
create it), then paste in each DAX formula from
[`dax_measures.dax`](dax_measures.dax) as a new measure on that table
(Modeling → New Measure). Read the comments in that file — a couple of
measures need you to confirm exact column/label values against
`documentation/database_schema.md` and the `reports/comparison/*.csv` files
before trusting the threshold/filter logic.

**Important:** filter out invalid models everywhere `model_metrics` or
`pipeline_comparison` is used for delay-severity — any Spark model trained
with `occupancy_pct` as an input is invalid (leakage: occupancy is only known
*after* the trip completes). `model_metrics.validity_flag = "INVALID"` marks
these; see [[phase6-7-ownership]] context in this project. Exclude them with a
report-level or page-level filter, not by deleting rows.

## 6. Build the pages (mirrors SRS steps 50–58)

| Page | SRS Step | Key tables |
|---|---|---|
| Executive | 50 | route_performance, overcrowding_summary, eda_route_delay, underutilized_services, recommendations, anomalies |
| Passenger Flow | 51 | od_matrix, eda_peak_hours, eda_peak_days, eda_stop_usage, flow_direction_demand |
| Route Performance | 52 | route_performance, route_reliability, route_clusters |
| Delay | 53 | eda_route_delay, delay_by_stop, delay_congestion_patterns, delay_top_trips |
| Occupancy | 54 | overcrowding_summary, persistent_overcrowding, demand_supply_gap, underutilized_services |
| Forecast | 55 | route_daily_boardings, pipeline_comparison (demand task) |
| Route Map | 56 | stops (latitude/longitude), eda_stop_usage, delay_by_stop |
| Spark vs Python | 43–44 | pipeline_comparison, model_metrics (filtered, see above) |

Add synced slicers (Step 57) for: route, stop, direction, day class /
peak-off-peak, delay level, occupancy level — use **View → Sync Slicers** so
one slicer selection applies across all pages that share the field.

Apply one consistent theme (**View → Themes → Customize current theme**) using
colors that match the React frontend, so the two look like one product.

## 7. Export deliverables

- Save the working file as `powerbi/UrbanTransitIQ.pbix`.
- **File → Export → Export to PDF** → save as
  `reports/UrbanTransitIQ_PowerBI.pdf`.
- Take one screenshot per page into `powerbi/screenshots/`.
- Commit `powerbi/UrbanTransitIQ.pbix`, `powerbi/screenshots/*`, and the PDF.
  Do **not** commit `powerbi_ro` credentials anywhere — Power BI stores the
  connection credentials locally in Windows Credential Manager, not in the
  `.pbix` file itself, so this is safe by default as long as you don't type
  the password into a text box on a page.

## 8. Sanity-check against the live site

Before treating any number as final, open the React Overview page
(`frontend/src/pages/OverviewPage.tsx`) side by side and confirm the
Executive Dashboard's top KPIs match. If they don't, the mismatch is almost
always a stale Import cache in Power BI (Home → Refresh) or a filter/relationship
issue — not a genuine numbers disagreement, since both read the same tables.
