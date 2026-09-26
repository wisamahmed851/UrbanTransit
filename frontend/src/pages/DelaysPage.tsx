import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChartFrame, ColumnChart, HBarChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Segmented } from '../components/ui'
import { label, minutes, num, pct, WEEKDAYS } from '../lib/format'
import { useRows } from '../lib/useApi'

type Dim = 'hour' | 'day_of_week' | 'time_period' | 'day_class' | 'route_type' | 'distance_band'
const ORDERED: Dim[] = ['hour', 'day_of_week', 'distance_band']
const TIME_ORDER = ['early_morning', 'morning_peak', 'midday', 'evening_peak', 'evening']

function dimLabel(dim: Dim, v: unknown): string {
  if (dim === 'hour') return `${Number(v)}:00`
  if (dim === 'day_of_week') return WEEKDAYS[Number(v)] ?? String(v)
  if (dim === 'distance_band') return `${v} km`
  return label(v)
}

export function DelaysPage() {
  const [dim, setDim] = useState<Dim>('hour')
  const byDim = useRows('delay_by_dimension', { limit: 1000 })
  const routes = useRows('eda_route_delay', { limit: 10, sort: '-late_share' })
  const stops = useRows('delay_by_stop', { limit: 1000, sort: '-congestion_record_rate' })
  const trips = useRows('delay_top_trips', { limit: 15, sort: '-delay_minutes' })

  const dimRows = (byDim.data?.rows ?? []).filter((r) => r.dimension === dim)
    .sort((a, b) => dim === 'time_period' ? TIME_ORDER.indexOf(String(a.dim_value)) - TIME_ORDER.indexOf(String(b.dim_value))
      : ORDERED.includes(dim) ? String(a.dim_value).localeCompare(String(b.dim_value), undefined, { numeric: true }) : Number(b.late_share) - Number(a.late_share))
  const chartData = dimRows.map((r) => ({ label: dimLabel(dim, r.dim_value), value: Number(r.late_share) }))
  const bottlenecks = (stops.data?.rows ?? []).filter((r) => r.is_bottleneck)

  return (
    <div className="page">
      <PageHead title="Delays">
        A trip counts as late when it arrives 5 minutes or more behind schedule. Cancelled trips and trips whose delay
        record failed quality checks are left out rather than counted as on time.
      </PageHead>
      {byDim.error && <ErrorNotice error={byDim.error} />}

      <Panel title="Where lateness concentrates" note="Share of trips 5+ minutes late."
        action={<Segmented label="Break down by" value={dim} onChange={setDim} options={[
          { value: 'hour', label: 'Hour' }, { value: 'day_of_week', label: 'Weekday' }, { value: 'time_period', label: 'Time of day' },
          { value: 'day_class', label: 'Day type' }, { value: 'route_type', label: 'Route type' }, { value: 'distance_band', label: 'Distance' },
        ]} />}>
        {byDim.loading && !byDim.data ? <Loading /> : (
          <ChartFrame
            chart={ORDERED.includes(dim) || dim === 'time_period'
              ? <ColumnChart name="Late share" data={chartData} format={(v) => pct(v, 0)} />
              : <HBarChart name="Late share" data={chartData} format={(v) => pct(v, 1)} />}
            rows={dimRows}
            columns={[
              { key: 'dim_value', label: label(dim), render: (r) => dimLabel(dim, r.dim_value) },
              { key: 'evaluated_trips', label: 'Trips checked', num: true, render: (r) => num(r.evaluated_trips) },
              { key: 'late_share', label: 'Late', num: true, render: (r) => pct(r.late_share) },
              { key: 'avg_delay_min', label: 'Average delay', num: true, render: (r) => minutes(r.avg_delay_min) },
              { key: 'p90_arrival_delay_min', label: '90th percentile', num: true, render: (r) => minutes(r.p90_arrival_delay_min) },
            ]}
          />
        )}
      </Panel>

      <div className="grid-2">
        <Panel title="Most often late routes">
          <DataTable rows={routes.data?.rows ?? []} columns={[
            { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}>{String(r.route_code)} ({String(r.route_id)})</Link> },
            { key: 'late_share', label: 'Late', num: true, render: (r) => pct(r.late_share) },
            { key: 'punctuality_rate', label: 'On time', num: true, render: (r) => pct(r.punctuality_rate) },
            { key: 'avg_delay_min', label: 'Average delay', num: true, render: (r) => minutes(r.avg_delay_min) },
          ]} />
        </Panel>

        <Panel title="Bottleneck stops" note="Top 5% of stops by congestion-related delay records, with at least 50 records.">
          <DataTable rows={bottlenecks.slice(0, 12)} empty="No bottleneck stops." columns={[
            { key: 'stop_name', label: 'Stop', render: (r) => `${r.stop_name} (${r.stop_id})` },
            { key: 'routes_serving', label: 'Routes', num: true },
            { key: 'congestion_record_rate', label: 'Congestion records per trip', num: true, render: (r) => num(r.congestion_record_rate, 2) },
            { key: 'top_reason', label: 'Main reason', render: (r) => label(r.top_reason) },
          ]} />
          {bottlenecks.length > 12 && <p className="panel-note">Showing the worst 12 of {bottlenecks.length}. All stops are on the Stops page.</p>}
        </Panel>
      </div>

      <Panel title="Most delayed trips" note="Single trips with the largest recorded delay.">
        <DataTable rows={trips.data?.rows ?? []} columns={[
          { key: 'service_date', label: 'Date' },
          { key: 'trip_id', label: 'Trip' },
          { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}>{String(r.route_id)}</Link> },
          { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
          { key: 'vehicle_id', label: 'Vehicle' },
          { key: 'delay_minutes', label: 'Delay', num: true, render: (r) => minutes(r.delay_minutes) },
          { key: 'delay_severity', label: 'Severity' },
        ]} />
      </Panel>
    </div>
  )
}

