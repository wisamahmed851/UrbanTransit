import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Row } from '../api/client'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, PageHead, Panel, Segmented } from '../components/ui'
import { label, num, pct } from '../lib/format'
import { useRows } from '../lib/useApi'

type View = 'bunching' | 'adherence' | 'travel'
const route = (r: Row) => <Link to={`/routes/${r.route_id}`}>{String(r.route_id)}</Link>

/** SRS steps 29, 31, 32, 33: headway and bunching, schedule adherence, scheduled vs actual travel time. */
export function ServicePage() {
 const [view, setView] = useState<View>('bunching')
 const [routeId, setRouteId] = useState('')
 const q = (sort: string) => ({ limit: 200, sort, route_id: routeId.trim().toUpperCase() || undefined })
 const bunching = useRows('headway_bunching', q('-bunched_share'))
 const adherence = useRows('schedule_adherence', q('-late_share'))
 const travel = useRows('travel_time_peak_offpeak', q('-peak_penalty_pct'))
 const active = { bunching, adherence, travel }[view]

 return (
  <div className="page">
   <PageHead title="Service quality">
    How evenly and how punctually vehicles run. Bunching is a gap between consecutive vehicles of under half the scheduled headway;
    an excessive gap is over one and a half times it. Worst routes come first.
   </PageHead>
   <div className="filters">
    <Segmented label="View" value={view} onChange={setView}
     options={[{ value: 'bunching', label: 'Headway and bunching' }, { value: 'adherence', label: 'Schedule adherence' }, { value: 'travel', label: 'Travel time' }]} />
    <label className="field">Route<input value={routeId} onChange={(e) => setRouteId(e.target.value)} placeholder="e.g. R012" /></label>
   </div>
   {active.error && <ErrorNotice error={active.error} />}
   {view === 'bunching' && (
    <Panel title="Headway and vehicle bunching" note="Per route, direction and time of day. Bunched share = gaps under 0.5x scheduled; gap share = gaps over 1.5x.">
     <DataTable rows={bunching.data?.rows ?? []} loading={bunching.loading} columns={[
      { key: 'route_id', label: 'Route', render: route },
      { key: 'direction', label: 'Direction' },
      { key: 'time_period', label: 'Time of day', render: (r) => label(r.time_period) },
      { key: 'avg_headway_min', label: 'Avg headway (min)', num: true, render: (r) => num(r.avg_headway_min, 1) },
      { key: 'headway_cv', label: 'Irregularity (CV)', num: true, render: (r) => num(r.headway_cv, 2) },
      { key: 'bunched', label: 'Bunched', num: true, render: (r) => num(r.bunched) },
      { key: 'bunched_share', label: 'Bunched share', num: true, render: (r) => pct(r.bunched_share) },
      { key: 'gap_share', label: 'Excess-gap share', num: true, render: (r) => pct(r.gap_share) },
     ]} />
    </Panel>
   )}
   {view === 'adherence' && (
    <Panel title="Schedule adherence" note="Arrivals compared with the timetable, per route and type of day.">
     <DataTable rows={adherence.data?.rows ?? []} loading={adherence.loading} columns={[
      { key: 'route_id', label: 'Route', render: route },
      { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
      { key: 'early_share', label: 'Early', num: true, render: (r) => pct(r.early_share) },
      { key: 'on_time_share', label: 'On time', num: true, render: (r) => pct(r.on_time_share) },
      { key: 'late_share', label: 'Late', num: true, render: (r) => pct(r.late_share) },
      { key: 'missed_trips', label: 'Missed trips', num: true, render: (r) => num(r.missed_trips) },
      { key: 'irregular_interval_share', label: 'Irregular intervals', num: true, render: (r) => pct(r.irregular_interval_share, 2) },
     ]} />
    </Panel>
   )}
   {view === 'travel' && (
    <Panel title="Peak against off-peak travel time" note="Scheduled and actual end-to-end minutes. Peak penalty = how much longer peak trips take than off-peak trips.">
     <DataTable rows={travel.data?.rows ?? []} loading={travel.loading} columns={[
      { key: 'route_id', label: 'Route', render: route },
      { key: 'direction', label: 'Direction' },
      { key: 'offpeak_scheduled_min', label: 'Off-peak scheduled', num: true, render: (r) => num(r.offpeak_scheduled_min, 1) },
      { key: 'offpeak_actual_min', label: 'Off-peak actual', num: true, render: (r) => num(r.offpeak_actual_min, 1) },
      { key: 'peak_scheduled_min', label: 'Peak scheduled', num: true, render: (r) => num(r.peak_scheduled_min, 1) },
      { key: 'peak_actual_min', label: 'Peak actual', num: true, render: (r) => num(r.peak_actual_min, 1) },
      { key: 'peak_penalty_pct', label: 'Peak penalty', num: true, render: (r) => pct(r.peak_penalty_pct, 0) },
     ]} />
    </Panel>
   )}
  </div>
 )
}
