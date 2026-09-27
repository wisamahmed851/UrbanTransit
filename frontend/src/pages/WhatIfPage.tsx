import { useState } from 'react'
import { api, ApiError } from '../api/client'
import type { WhatIfResponse, WhatIfState } from '../api/types'
import { DataTable } from '../components/DataTable'
import { EstimateTag } from '../components/ModelCard'
import { TripFields } from '../components/TripForm'
import { DEFAULT_TRIP, type TripInput } from '../lib/trip'
import { ErrorNotice, PageHead, Panel } from '../components/ui'
import { num, pct } from '../lib/format'

/** SRS steps 48-49. Each scenario has at most one number to set. */
const SCENARIOS: { value: string; label: string; param?: { name: string; label: string; min: number; max: number; step: number; initial: number } }[] = [
 { value: 'increase_frequency', label: 'Increase frequency', param: { name: 'trips', label: 'Extra trips per hour', min: 1, max: 30, step: 1, initial: 1 } },
 { value: 'decrease_frequency', label: 'Decrease frequency', param: { name: 'trips', label: 'Fewer trips per hour', min: 1, max: 30, step: 1, initial: 1 } },
 { value: 'add_vehicle', label: 'Add a vehicle' },
 { value: 'change_vehicle_capacity', label: 'Change vehicle capacity', param: { name: 'capacity', label: 'Places per vehicle', min: 10, max: 300, step: 5, initial: 120 } },
 { value: 'shift_trip_time', label: 'Shift trip start time', param: { name: 'minutes', label: 'Minutes (negative = earlier)', min: -180, max: 180, step: 15, initial: 60 } },
 { value: 'remove_low_demand_trip', label: 'Remove a low-demand trip' },
 { value: 'increase_demand', label: 'Increase predicted demand', param: { name: 'percent', label: 'Demand change (%)', min: -90, max: 300, step: 5, initial: 20 } },
]

const MEASURES: { key: keyof WhatIfState; label: string; fmt: (v: number | string) => string }[] = [
 { key: 'hour', label: 'Departure hour', fmt: (v) => `${String(v).padStart(2, '0')}:00` },
 { key: 'trips_per_hour', label: 'Trips per hour', fmt: (v) => num(v, 1) },
 { key: 'headway_min', label: 'Headway (min)', fmt: (v) => num(v, 1) },
 { key: 'waiting_time_min', label: 'Average wait (min)', fmt: (v) => num(v, 1) },
 { key: 'capacity_per_trip', label: 'Places per vehicle', fmt: (v) => num(v) },
 { key: 'capacity_per_hour', label: 'Route capacity per hour', fmt: (v) => num(v) },
 { key: 'demand_per_hour', label: 'Passenger load per hour', fmt: (v) => num(v) },
 { key: 'peak_load_per_trip', label: 'Peak load per trip', fmt: (v) => num(v, 1) },
 { key: 'occupancy', label: 'Occupancy', fmt: (v) => pct(v, 0) },
 { key: 'occupancy_category', label: 'Occupancy level', fmt: (v) => String(v) },
 { key: 'demand_coverage', label: 'Demand coverage', fmt: (v) => pct(v, 0) },
 { key: 'crowding_probability', label: 'Overcrowding risk (model)', fmt: (v) => (v == null ? '-' : pct(v, 0)) },
 { key: 'delay_risk', label: 'Moderate or severe delay risk (model)', fmt: (v) => (v == null ? '-' : pct(v, 0)) },
]

export function WhatIfPage() {
 const [trip, setTrip] = useState<TripInput>(DEFAULT_TRIP)
 const [scenario, setScenario] = useState(SCENARIOS[0].value)
 const spec = SCENARIOS.find((s) => s.value === scenario)!
 const [value, setValue] = useState<number>(spec.param?.initial ?? 0)
 const [result, setResult] = useState<WhatIfResponse | null>(null)
 const [error, setError] = useState<ApiError | null>(null)
 const [busy, setBusy] = useState(false)

 const pick = (v: string) => {
  setScenario(v)
  setValue(SCENARIOS.find((s) => s.value === v)!.param?.initial ?? 0)
  setResult(null)
 }
 const run = async (e: React.FormEvent) => {
  e.preventDefault()
  setBusy(true); setError(null)
  try {
   const params = spec.param ? { [spec.param.name]: value } : {}
   setResult(await api<WhatIfResponse>('/whatif', { method: 'POST', body: JSON.stringify({ ...trip, scenario, params }) }))
  } catch (err) {
   setResult(null); setError(err as ApiError)
  } finally { setBusy(false) }
 }

 return (
  <div className="page">
   <PageHead title="What-if scenarios">
    Change one thing about a route's service in one hour and see the likely effect on occupancy, waiting time,
    capacity and risk. It starts from what was observed on that route and hour over the last 8 weeks. Every result
    is an estimate, not an observation.
   </PageHead>

   <Panel title="Scenario">
    <form className="filters" onSubmit={run}>
     <label className="field">Change
      <select value={scenario} onChange={(e) => pick(e.target.value)}>
       {SCENARIOS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
     </label>
     {spec.param && (
      <label className="field">{spec.param.label}
       <input type="number" value={value} min={spec.param.min} max={spec.param.max} step={spec.param.step}
        onChange={(e) => setValue(Number(e.target.value))} />
      </label>
     )}
     <TripFields value={trip} onChange={setTrip} />
     <button className="btn" type="submit" disabled={busy}>{busy ? 'Simulating…' : 'Simulate'}</button>
    </form>
    <p className="panel-note">Adding a new stop is not simulated: no model or measure here can estimate a stop that has no history.</p>
   </Panel>

   {error && <ErrorNotice error={error} />}
   {result && <Result r={result} />}
  </div>
 )
}

function Result({ r }: { r: WhatIfResponse }) {
 const changed = new Set(r.changes.map((c) => c.measure))
 const rows = MEASURES.map((m) => ({
  measure: m.label, before: m.fmt(r.baseline[m.key] as number), after: m.fmt(r.result[m.key] as number),
  changed: changed.has(m.key) ? 'changed' : '',
 }))
 const s = r.scenario
 return (
  <Panel title="Estimated effect" note={`Route ${s.route_id}, direction ${s.direction}, ${s.day_type} ${String(s.hour).padStart(2, '0')}:00. Baseline observed ${r.observed_window}.`}
   action={<EstimateTag>{r.label}</EstimateTag>}>
   {r.notes.length > 0 && (
    <div className="notice notice-info" role="note">{r.notes.map((n) => <span key={n}>{n}</span>)}</div>
   )}
   <DataTable rows={rows} columns={[
    { key: 'measure', label: 'Measure', sortable: false },
    { key: 'before', label: 'Now (baseline)', num: true, sortable: false },
    { key: 'after', label: 'After the change (estimate)', num: true, sortable: false, render: (x) => x.changed ? <b>{x.after}</b> : x.after },
   ]} />
   <ul className="panel-note">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
  </Panel>
 )
}
