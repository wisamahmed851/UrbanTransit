# Backend API (Flask), CMD-019

REST API over the MySQL copy of the pipeline outputs. Everything lives under `/api`; the
React dev server (`http://localhost:5173` or `:3000`, set in `CORS_ORIGINS`) may call it.

| Flask concept | Laravel | NestJS |
|---|---|---|
| Blueprint (`src/blueprints/*.py`) | route group + controller | module + controller |
| SQLAlchemy model (`src/models/*.py`) | Eloquent model | TypeORM entity |
| Flask-Migrate (`database/migrations`) | migrations | TypeORM migrations |
| `@permission_required(...)` (`src/security.py`) | `can:` middleware / policy | guard + `@Roles()` |
| `register_error_handlers` (`src/errors.py`) | exception handler | global exception filter |
| `flask rbac seed`, `flask users create` (`src/cli.py`) | Artisan commands | CLI commands |

## Running

```bash
# inside WSL, repo root, venv active; MySQL running
flask db upgrade                                  # schema
flask rbac seed                                   # 4 roles, 9 permissions (config/rbac.yaml)
flask users create alice --role admin             # prompts for the password
python database/load_analytics_to_mysql.py --reference   # needs HDFS started
python database/load_model_metrics.py
flask run                                         # http://127.0.0.1:5000  (or python src/app.py)
python -m pytest                                  # 60 tests, in-memory SQLite
```

## Conventions

- **Auth:** `POST /api/auth/login` returns `access_token`. Send `Authorization: Bearer <token>`.
  Tokens last `JWT_ACCESS_TOKEN_MINUTES` (default 60). The user is reloaded on every request,
  so deactivating an account or changing a role takes effect immediately.
- **Errors:** always `{"error": {"code": "...", "message": "...", "details": {...}}}` with the
  HTTP status. Common codes: `unauthorized`, `invalid_token`, `token_expired`, `forbidden`,
  `not_found`, `unknown_table`, `unsupported_filter`, `invalid_parameter`, `validation_failed`,
  `conflict`, `internal_error`.
- **Numbers:** decimals are JSON numbers; CSV writes the exact stored digits. Dates are `YYYY-MM-DD`. NULL is `null` in JSON and an empty cell in CSV.

## Roles and permissions

| permission | admin | operator | analyst | evaluator |
|---|:-:|:-:|:-:|:-:|
| analytics:read | ✓ | ✓ | ✓ | ✓ |
| reports:export | ✓ | ✓ | ✓ | ✓ |
| models:read | ✓ | ✓ | ✓ | ✓ |
| reference:read | ✓ | ✓ | ✓ | ✓ |
| reference:write | ✓ | | | |
| users:manage | ✓ | | | |
| audit:read | ✓ | | | ✓ |
| predictions:use | ✓ | ✓ | | |
| recommendations:read | ✓ | ✓ | ✓ | |

## Endpoints

### Health and auth

| method | path | access | notes |
|---|---|---|---|
| GET | `/api/health` (also `/health`) | public | 200 when MySQL answers, 503 otherwise |
| POST | `/api/auth/login` | public | `{"username","password"}` → token + user; failed attempts are audited |
| GET | `/api/auth/me` | any user | user with roles and permissions |

### Analytics (real data: Phase 5, 30 tables)

| method | path | permission |
|---|---|---|
| GET | `/api/analytics` | analytics:read. Every table with its columns (Spark types), row count and supported filters |
| GET | `/api/analytics/<table>` | analytics:read. Rows: `{table, total, limit, offset, filters, rows}` |

Query parameters, each accepted only by tables that have the column:

| parameter | applies to |
|---|---|
| `route_id` | tables with `route_id` |
| `stop_id` | `stop_id`; on `od_matrix` / `flow_od_pairs` it matches origin **or** destination |
| `direction` | `0` or `1` |
| `day_class` | `weekday`, `weekend`, `holiday` |
| `time_period` | `early_morning`, `morning_peak`, `midday`, `evening_peak`, `evening` |
| `date_from`, `date_to` | tables with `service_date` (`eda_peak_days`, `special_event_dates`, `anomalies`, `delay_top_trips`), inclusive |
| `sort` | e.g. `-composite_score,route_id` |
| `limit`, `offset` | default 100, max 1000 |

A filter the table cannot honour returns **400 `unsupported_filter`** and lists the supported
filters. It is never silently ignored. The table list and the reasons for skipping 11 tables
are in `documentation/database_schema.md`.

### Network map (real data; CMD-022)

| method | path | permission | notes |
|---|---|---|---|
| GET | `/api/network/geometry` | analytics:read | GeoJSON: 236 route LineStrings (118 routes x 2 directions, drawn stop to stop from `route_stops`) with type, class, score; 756 stop Points with type, zone, routes, estimated passengers, bottleneck flag. Cached 10 min |
| GET | `/api/network/replay` | analytics:read | the replay window: first/last ping, pings per day, vehicles |
| GET | `/api/network/vehicles?at=YYYY-MM-DDTHH:MM:SS&window=180` | analytics:read | latest ping of each bus in the `window` seconds (30-900, default 180) up to `at`; 400 `outside_replay_window` outside the sample |

The GPS data is the Phase 1 generator's **simulated AVL sample covering 10-16 Nov 2025
only** (1,139,087 pings, 728 vehicles). There is no real-time feed, so every response carries
a `source` saying it is a replay, and the UI always shows the replay date. Nothing is labelled "live".

### Reports (CSV)

| method | path | permission |
|---|---|---|
| GET | `/api/reports` | reports:export. Exportable tables |
| GET | `/api/reports/<table>.csv` | reports:export. Same filters and sort as above; streams every matching row; audited |

### Models (real evidence: Phase 6, read-only)

| method | path | permission |
|---|---|---|
| GET | `/api/models/metrics` | models:read. Filters `task`, `algorithm`, `split_type`, `metric_name`, `source_file`, `validity_flag` |
| GET | `/api/models/clusters` | models:read. The 4 K-Means (k=4) cluster profiles |

> **The delay-severity numbers do not reflect a valid model.** All 169 `delay_severity`
> metric rows (every algorithm, including the 2026-09-26 retrains) carry
> `validity_flag: "INVALID"`. Those models use `occupancy_pct`, a same-trip outcome, as an
> input (occupancy leakage). The API shows the metrics for transparency, and
> `/api/models/metrics` adds a `warnings` entry whenever such rows are returned. They must not
> be used to serve predictions until the model is retrained without that feature.

`/api/models/clusters` returns profiles only. No route-to-cluster assignment exists yet, so
the API cannot say which routes belong to a cluster.

### Admin

| method | path | permission |
|---|---|---|
| GET | `/api/admin/{routes,stops,vehicles}` | reference:read. `?q=` searches id and name; paged |
| GET | `/api/admin/{routes,stops,vehicles}/<id>` | reference:read. Routes include their `route_performance` and `route_reliability` rows; stops include `stop_performance` |
| POST | `/api/admin/{routes,stops,vehicles}` | reference:write. Validated against `documentation/schemas/<table>.json` (required fields, types, `a \| b` enums) |
| PATCH | `/api/admin/{routes,stops,vehicles}/<id>` | reference:write. Partial update; the id and `dq_flags` are read-only |
| DELETE | `/api/admin/{routes,stops,vehicles}/<id>` | reference:write. 409 if a stop is still a route terminus |
| GET, POST | `/api/admin/users` | users:manage |
| PATCH | `/api/admin/users/<id>` | users:manage. `roles`, `is_active`, `email`, `password` |
| GET | `/api/admin/audit-log` | audit:read. `?actor=&action=`, newest first |

Reference edits change the MySQL copy only; they are not written back to HDFS.

### Stubs (no real data yet)

These return **HTTP 503** with `{"status": "unavailable", "stub": true, "feature", "reason"}`.
They never return a made-up result.

| method | path | permission | reason |
|---|---|---|---|
| POST | `/api/predictions/delay` | predictions:use | `unavailable - underlying models flagged invalid (occupancy_pct leakage), pending retrain` |
| POST | `/api/predictions/crowding` | predictions:use | `unavailable - Phase 7 pipeline and full prediction set not yet produced` |
| GET | `/api/recommendations` | recommendations:read | `unavailable - Phase 7 recommendation engine not yet built` |
