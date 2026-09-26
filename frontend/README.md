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
| Overview, Routes, route detail, Delays, Crowding and capacity, Stops, Demand and journeys, Passengers | Phase 5 analytics tables, live from the API |
| Model results | Phase 6 metric files and cluster profiles, live from the API; delay models shown as not valid |
| Data explorer | any of the 30 analytics tables, with filters and CSV export |
| Routes, stops, vehicles / Users / Audit log | admin API (role-gated) |
| **Predictions, Recommendations** | **sample data**: the API answers 503 "unavailable" for these, so the page shows generated figures inside a hatched "Sample data, not pipeline output" frame |

Sample data lives only in `src/sample/sampleData.ts` and is used only when the API returns its
explicit stub response. When the real endpoints return data, the pages show it instead;
delete the sample module then.

## Structure

| path | role |
|---|---|
| `src/api/` | fetch wrapper (token, error envelope, stub detection) and response types |
| `src/auth/` | session context; hides what a role cannot do (the API enforces it) |
| `src/components/` | shell with the transit-line navigation, tables, filter bar, charts, badges |
| `src/pages/` | one file per screen |
| `src/lib/` | fetch hooks and value formatting |
| `src/styles/` | design tokens (light and dark) and the stylesheet |

Charts follow the validated dataviz palette (4 categorical slots, checked in light and dark
mode). Every chart has a table view, and route-type colours always come with the route code.
