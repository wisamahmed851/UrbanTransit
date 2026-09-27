# UrbanTransit IQ: web dashboard

React 19 + TypeScript + Vite single-page app over the Flask API (`documentation/backend_api.md`).

## Run

```bash
# 1. API, inside WSL (MySQL running, data loaded)
cd /mnt/d/Techwise_2026 && source ~/venvs/urbantransit/bin/activate && flask run

# 2. Dashboard, on Windows
cd D:\Techwise_2026\frontend
npm install            # first time only (cache is on D:, see .npmrc)
npm run dev            # http://localhost:5173
```

Vite proxies `/api` to `http://127.0.0.1:5000` (WSL forwards that port to Windows), so the
browser talks to one origin. Point it elsewhere with `API_URL=http://host:port npm run dev`.
Sign in with an account made by `flask users create <name> --role admin`.

`npm run build` type-checks and writes `dist/`; `npm run lint` runs oxlint.

## Where the data comes from

| page | source |
|---|---|
| Network map | route lines, stops and a **replay** of the 7-day GPS sample (10-16 Nov 2025); never "live", the replay date is always on screen |
| Overview, Routes, route detail, Delays, Crowding and capacity, Stops, Demand and journeys, Passengers | Phase 5 analytics tables, live from the API |
| Model results | Spark (Phase 6) and Python (Phase 7) metrics with the SRS target check, the served-model registry, both sets of route groups |
| Predictions, Demand forecast, What-if | the saved Phase 7 models, served by the API; every figure labelled an estimate |
| Recommendations, Critical alerts on Overview | the Phase 9 engine output |
| Spark vs Python | the Phase 8 comparison cases |
| Data explorer | any of the 30 analytics tables, with filters and CSV export |
| Routes, stops, vehicles / Users / Audit log | admin API (role-gated) |
No page uses sample data since CMD-024 (the sample module was deleted). The API client still
recognises the backend's explicit 503 stub response, should a new endpoint start as one.

## Tables, motion, public page (CMD-026)

- **Tables** use DataTables (`datatables.net` core + `datatables.net-react`, no default CSS;
  theme in `styles/app.css`). Local tables sort, and above 10 rows search and page; server
  tables (Data explorer, O-D) send header clicks to the API sort. See `components/DataTable.tsx`.
- **Motion**: transform/opacity only; reduced motion keeps short fades and drops movement.
- **Public page** `/welcome` (signed-out visitors to `/` land there) with figures from
  `GET /api/public/summary`. Product shots in `public/site/` are screenshots of this app;
  retake them after major UI changes.

## Structure

| path | role |
|---|---|
| `src/api/` | fetch wrapper (token, error envelope, stub detection) and response types |
| `src/auth/` | session context; hides what a role cannot do (the API enforces it) |
| `src/components/` | shell with the transit-line navigation, tables, filter bar, charts, badges |
| `src/pages/` | one file per screen |
| `src/lib/` | fetch hooks and value formatting |
| `src/styles/` | design tokens (light and dark) and the stylesheet |

## Theme (CMD-022)

- **Palette:** generated with the ui-color-palette MCP from blue `#2b53d9` and gold `#f5b301`
  (`src/styles/tokens.css` lists every step and contrast). Blue is the only primary, gold the
  only accent (CTAs, active station, focus, emphasis), warning is orange so it never reads as gold.
- **Charts:** two validated brand hues (dark: `#5181ff` / `#bc7f00`), a third series is
  navy-grey and dashed. Every chart has a table view.
- **Glass:** backdrop blur with a 1px light edge and inner highlight (a web approximation of
  frosted glass). Solid fallback when blur is unsupported or with `prefers-reduced-transparency`.
- **Motion** (`motion/react`): scroll-reveal stagger, KPI counters, 450 ms chart transitions,
  hover lift. All static under `prefers-reduced-motion`.
- **Dark by default**, light and "match system" in the sidebar.

## Network map

MapLibre GL + CARTO Dark Matter (free, no key), recoloured to the navy palette. If the style
cannot be fetched in 4 s (offline, blocked) a self-contained navy style is used and the whole
network still renders; this was tested with every non-localhost request aborted. Route types
are told apart by weight and dash (BRT thick gold, trunk blue, local thin blue, feeder dashed
grey). The replay day, time and route are in the URL, e.g. `/map?day=2025-11-14&t=17:30&route=R001`.

Vite note: MapLibre is excluded from dependency pre-bundling (`vite.config.ts`) and its worker
is bundled via `?worker&url` (`src/components/map/basemap.ts`); otherwise the worker fails to load.
