/**
 * The "which trip" fields shared by Predictions and What-if: route, direction, date, departure hour.
 * The route list comes from the reference API; the date defaults to tomorrow.
 */

import type { ReactNode } from 'react'
import { useRouteOptions, type TripInput } from '../lib/trip'

export function RouteSelect({ value, onChange, allowAll }: { value: string; onChange: (v: string) => void; allowAll?: boolean }) {
  const routes = useRouteOptions()
  return routes.data ? (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowAll && <option value="">All routes</option>}
      {routes.data.rows.map((r) => <option key={r.route_id} value={r.route_id}>{r.route_id} · {r.route_name}</option>)}
    </select>
  ) : <input value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} spellCheck={false} placeholder="R001" />
}

export function TripFields({ value, onChange, children }: { value: TripInput; onChange: (v: TripInput) => void; children?: ReactNode }) {
  return (
    <>
      <label className="field">Route<RouteSelect value={value.route_id} onChange={(route_id) => onChange({ ...value, route_id })} /></label>
      <label className="field">Direction
        <select value={value.direction} onChange={(e) => onChange({ ...value, direction: Number(e.target.value) })}>
          <option value={0}>Outbound (0)</option><option value={1}>Inbound (1)</option>
        </select>
      </label>
      <label className="field">Date<input type="date" value={value.service_date} required onChange={(e) => onChange({ ...value, service_date: e.target.value })} /></label>
      <label className="field">Departure hour
        <select value={value.hour} onChange={(e) => onChange({ ...value, hour: Number(e.target.value) })}>
          {Array.from({ length: 24 }, (_, h) => h).map((h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}
        </select>
      </label>
      {children}
    </>
  )
}
