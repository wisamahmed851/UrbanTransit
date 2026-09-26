import { Link, useParams } from 'react-router-dom'
import type { Row } from '../api/client'
import { ChartFrame, HBarChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, Loading, Panel, RouteBadge, RouteClass, Stats } from '../components/ui'
import { label, minutes, num, pct } from '../lib/format'
import { useApi, useRows } from '../lib/useApi'

const COMPONENTS: [string, string][] = [
  ['demand_score', 'Demand'], ['occupancy_score', 'Occupancy'], ['punctuality_score', 'Punctuality'],
  ['delay_frequency_score', 'Delay frequency'], ['travel_time_score', 'Travel time'], ['reliability_score', 'Reliability'],
  ['load_score', 'Passenger load'], ['underutilization_score', 'Underuse'], ['overcrowding_score', 'Overcrowding'],
]

export function RouteDetailPage() {
  const { routeId = '' } = useParams()
  const detail = useApi<{ row: Row; analytics: { route_performance: Row | null; route_reliability: Row | null } }>(`/admin/routes/${routeId}`)
  const q = { route_id: routeId, limit: 1000 }
  const overcrowding = useRows('overcrowding_summary', q)
  const congestion = useRows('delay_congestion_patterns', q)
  const gap = useRows('demand_supply_gap', { ...q, sort: '-utilization' })
  const travel = useRows('travel_time_peak_offpeak', q)

  if (detail.error) return <div className="page"><ErrorNotice error={detail.error} /><Link to="/routes">Back to routes</Link></div>
  if (!detail.data) return <Loading what="route" />

  const route = detail.data.row
  const perf = detail.data.analytics.route_performance ?? {}
  const rel = detail.data.analytics.route_reliability ?? {}
  const scores = COMPONENTS.map(([k, l]) => ({ label: l, value: Number(perf[k] ?? NaN) })).filter((s) => Number.isFinite(s.value))
  const cong = congestion.data?.rows[0]

  return (
    <div className="page">
      <Link to="/routes" style={{ fontSize: 'var(--fs-sm)' }}>All routes</Link>
      <header className="page-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <RouteBadge code={route.route_code} type={route.route_type} id={route.route_id} />
          <h1>{String(route.route_name)}</h1>
        </div>
        <p>{label(route.route_type)} route {String(route.route_id)}, {num(route.distance_km, 1)} km, running since {String(route.launch_date)}.</p>
      </header>

      <Stats items={[
        { label: 'Class', value: <RouteClass value={perf.route_class} />, sub: perf.overcrowded_flag ? `Overcrowded flag: ${label(perf.overcrowded_scope)}` : 'No persistent overcrowding' },
        { label: 'Composite score', value: num(perf.composite_score, 1), sub: perf.composite_rank != null ? `better than ${pct(perf.composite_rank, 0)} of routes` : undefined },
        { label: 'Boardings per day', value: num(perf.med_daily_boardings), sub: 'median over normal days' },
        { label: 'On time', value: pct(rel.on_time_rate), sub: `${pct(rel.missed_share)} of trips missed` },
      ]} />

      {perf.class_reason && (
        <div className="notice notice-info"><strong>Why this class</strong><span>{String(perf.class_reason)}</span>
          {perf.tricky_case_notes && <span style={{ color: 'var(--ink-muted)' }}>{String(perf.tricky_case_notes)}</span>}</div>
      )}

      <div className="grid-2">
        <Panel title="The nine scores" note="0 to 100, where 100 is best. The composite is their weighted mean.">
          <ChartFrame
            chart={<HBarChart name="Score" data={scores} format={(v) => num(v, 1)} />}
            rows={scores as unknown as Row[]}
            columns={[{ key: 'label', label: 'Measure' }, { key: 'value', label: 'Score', num: true, render: (r) => num(r.value, 1) }]}
          />
        </Panel>

        <Panel title="Delays and travel time">
          <DataTable rows={[
            { m: 'Median share of trips late (5+ min)', v: pct(perf.med_late_share) },
            { m: 'Arrival delay spread (std)', v: minutes(rel.arrival_delay_std) },
            { m: 'Early arrivals', v: pct(rel.early_arrival_share) },
            { m: 'Late arrivals', v: pct(rel.late_arrival_share) },
            { m: 'Congestion pattern', v: cong ? label(cong.congestion_pattern) : '–' },
            { m: 'Morning peak delay vs midday', v: cong ? `+${minutes(cong.morning_excess_min)}` : '–' },
            { m: 'Evening peak delay vs midday', v: cong ? `+${minutes(cong.evening_excess_min)}` : '–' },
            ...(travel.data?.rows ?? []).map((t) => ({ m: `Peak travel penalty, direction ${t.direction}`, v: pct(t.peak_penalty_pct) })),
          ]} columns={[{ key: 'm', label: 'Measure', sortable: false }, { key: 'v', label: 'Value', num: true, sortable: false }]} />
        </Panel>
      </div>

      <Panel title="Crowding by direction">
        <DataTable rows={overcrowding.data?.rows ?? []} columns={[
          { key: 'direction', label: 'Direction' },
          { key: 'measured_trips', label: 'Counted trips', num: true, render: (r) => num(r.measured_trips) },
          { key: 'avg_occupancy', label: 'Average load', num: true, render: (r) => pct(r.avg_occupancy) },
          { key: 'overload_share', label: 'Trips overloaded', num: true, render: (r) => pct(r.overload_share) },
          { key: 'critical_trips', label: 'Critical trips', num: true, render: (r) => num(r.critical_trips) },
          { key: 'max_occupancy', label: 'Highest load', num: true, render: (r) => pct(r.max_occupancy, 0) },
        ]} />
      </Panel>

      <Panel title="Capacity by time of day" note="Load at the busiest point of each trip compared with the seats and standing room scheduled.">
        {gap.loading && !gap.data ? <Loading /> : (
          <DataTable rows={gap.data?.rows ?? []} columns={[
            { key: 'direction', label: 'Dir.' },
            { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
            { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
            { key: 'trips_per_hour', label: 'Trips / hour', num: true, render: (r) => num(r.trips_per_hour, 1) },
            { key: 'utilization', label: 'Use of capacity', num: true, render: (r) => pct(r.utilization, 0) },
            { key: 'gap_status', label: 'Status', render: (r) => label(r.gap_status) },
            { key: 'suggestion', label: 'Phase 5 suggestion', render: (r) => label(r.suggestion) },
          ]} />
        )}
      </Panel>
    </div>
  )
}
