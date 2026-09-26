import { ChartLineUp, Crown, Path, Siren, UsersThree } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Row } from '../api/client'
import { ChartFrame, HBarChart, LinesChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { loadBasemap, type Basemap } from '../components/map/basemap'
import { ROUTE_TYPES, TransitMap, type Geometry } from '../components/map/TransitMap'
import { Empty, ErrorNotice, Loading, PageHead, Panel, RouteBadge, RouteClass, Stats } from '../components/ui'
import { label, num, ROUTE_CLASSES } from '../lib/format'
import { useApi, useRows } from '../lib/useApi'

const ALL_TYPES = new Set(ROUTE_TYPES.map((t) => t.type))
const whole = (n: number) => num(Math.round(n))

/** Small, non-interactive view of the network that links to the full map. */
function NetworkPreview() {
  const [basemap, setBasemap] = useState<Basemap | null>(null)
  const geometry = useApi<Geometry>('/network/geometry')
  useEffect(() => { let live = true; loadBasemap().then((b) => live && setBasemap(b)); return () => { live = false } }, [])
  return (
    <Panel title="The network"
      note="118 routes by type: BRT in gold, trunk and local in blue, feeder dashed."
      action={<Link className="btn" to="/map">Open network map</Link>}>
      <div className="map-shell compact">
        {basemap ? <TransitMap basemap={basemap} geometry={geometry.data} types={ALL_TYPES} showStops={false} interactive={false} zoom={9.5} />
          : <Loading what="map" />}
      </div>
    </Panel>
  )
}

export function OverviewPage() {
  const perf = useRows('route_performance', { limit: 1000, sort: 'composite_score' })
  const days = useRows('eda_peak_days', { limit: 1000, sort: 'service_date' })
  const hours = useRows('eda_peak_hours', { limit: 1000 })
  const events = useRows('special_event_dates', { limit: 20, sort: '-routes_spiking' })
  const anomalies = useRows('anomaly_summary', { limit: 50 })

  const error = perf.error ?? days.error ?? hours.error
  const routes = perf.data?.rows ?? []
  const eligible = routes.filter((r) => r.eligible)
  const byClass = ROUTE_CLASSES.map((c) => ({
    label: c, value: routes.filter((r) => r.route_class === c).length,
    flagged: routes.filter((r) => r.route_class === c && r.overcrowded_flag).length,
  })).filter((c) => c.value > 0).sort((a, b) => b.value - a.value)

  const dayRows = days.data?.rows ?? []
  const avgDaily = dayRows.length ? dayRows.reduce((s, r) => s + Number(r.est_system_boardings ?? 0), 0) / dayRows.length : null
  const signals = (anomalies.data?.rows ?? []).reduce((s, r) => s + Number(r.signals ?? 0), 0)

  // demand by hour: one row per hour, one column per day class
  const hourly = Array.from({ length: 24 }, (_, h) => {
    const at = (d: string) => (hours.data?.rows ?? []).find((r) => r.hour === h && r.day_class === d)?.est_boardings_per_day ?? null
    return { hour: String(h), weekday: at('weekday'), weekend: at('weekend'), holiday: at('holiday') } as Record<string, string | number | null>
  }).filter((r) => r.weekday !== null || r.weekend !== null || r.holiday !== null)

  const attention = routes
    .filter((r) => r.route_class === 'Overcrowded' || r.route_class === 'Low Performing' || r.route_class === 'High Demand but Unreliable')
    .slice(0, 10)

  return (
    <div className="page">
      <PageHead title="Network overview">
        A year of service, 1 Sep 2025 to 31 Aug 2026, scored from normal operating days. Special events and holidays are left out of route scores.
      </PageHead>

      {error && <ErrorNotice error={error} />}

      <Stats items={[
        { label: 'Routes scored', icon: Path, value: perf.data ? eligible.length : '…', format: whole,
          sub: perf.data ? `${routes.length - eligible.length} with too little data` : undefined },
        { label: 'High performing', icon: Crown, value: perf.data ? routes.filter((r) => r.route_class === 'High Performing').length : '…', format: whole,
          sub: 'top 30% by composite score' },
        { label: 'Persistently overcrowded', icon: UsersThree, value: perf.data ? routes.filter((r) => r.overcrowded_flag).length : '…', format: whole,
          sub: 'routes with a recurring overload pattern' },
        { label: 'Boardings per day', icon: ChartLineUp, value: avgDaily ?? '…', format: whole,
          sub: 'estimated system average, 1 Sep 2025 to 31 Aug 2026', spark: dayRows.map((r) => Number(r.est_system_boardings ?? 0)) },
        { label: 'Anomaly signals', icon: Siren, value: anomalies.data ? signals : '…', format: whole,
          sub: `${anomalies.data?.rows.length ?? 0} kinds, see Demand` },
      ]} />

      <NetworkPreview />

      <div className="grid-2">
        <Panel title="How the routes score" note="Each route gets one class. Overcrowding is also flagged separately, whatever the class.">
          {perf.loading && !perf.data ? <Loading /> : (
            <ChartFrame
              chart={<HBarChart name="Routes" data={byClass} format={(v) => num(v)} />}
              rows={byClass as unknown as Row[]}
              columns={[
                { key: 'label', label: 'Class', render: (r) => <RouteClass value={r.label} /> },
                { key: 'value', label: 'Routes', num: true },
                { key: 'flagged', label: 'Also flagged overcrowded', num: true },
              ]}
            />
          )}
        </Panel>

        <Panel title="When people travel" note="Estimated boardings per day in each hour, by type of day.">
          {hours.loading && !hours.data ? <Loading /> : (
            <ChartFrame
              legend={[{ label: 'Weekday', slot: 0 }, { label: 'Weekend', slot: 1 }, { label: 'Holiday', slot: 2 }]}
              chart={<LinesChart data={hourly} xKey="hour" format={(v) => num(v)} xFormat={(h) => `${h}:00`}
                series={[{ key: 'weekday', label: 'Weekday', slot: 0 }, { key: 'weekend', label: 'Weekend', slot: 1 }, { key: 'holiday', label: 'Holiday', slot: 2 }]} />}
              rows={hourly as Row[]}
              columns={[
                { key: 'hour', label: 'Hour', render: (r) => `${r.hour}:00` },
                { key: 'weekday', label: 'Weekday', num: true, render: (r) => num(r.weekday) },
                { key: 'weekend', label: 'Weekend', num: true, render: (r) => num(r.weekend) },
                { key: 'holiday', label: 'Holiday', num: true, render: (r) => num(r.holiday) },
              ]}
            />
          )}
        </Panel>

        <Panel title="Daily ridership across the year" note="Estimated system boardings per service day." className="span-2">
          {days.loading && !days.data ? <Loading /> : (
            <ChartFrame
              chart={<LinesChart data={dayRows as Record<string, string | number | null>[]} xKey="service_date" format={(v) => num(v)}
                series={[{ key: 'est_system_boardings', label: 'Boardings', slot: 0 }]} />}
              rows={dayRows}
              columns={[
                { key: 'service_date', label: 'Date' },
                { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
                { key: 'holiday_name', label: 'Holiday' },
                { key: 'est_system_boardings', label: 'Boardings', num: true, render: (r) => num(r.est_system_boardings) },
                { key: 'busiest_rank', label: 'Busiest rank', num: true },
              ]}
            />
          )}
        </Panel>

        <Panel title="Routes that need attention" note="Overcrowded, low performing, or busy but unreliable, lowest score first.">
          {perf.data && !attention.length ? <Empty>No routes in these classes.</Empty> : (
            <DataTable rows={attention} columns={[
              { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}><RouteBadge code={r.route_code} type={r.route_type} id={r.route_id} /></Link> },
              { key: 'route_class', label: 'Class', render: (r) => <RouteClass value={r.route_class} /> },
              { key: 'composite_score', label: 'Score', num: true, render: (r) => num(r.composite_score, 1) },
            ]} />
          )}
        </Panel>

        <Panel title="Busiest event days" note="Days when demand spiked on many routes at once, against the same weekday's usual level.">
          <DataTable rows={(events.data?.rows ?? []).filter((r) => r.date_status !== 'normal').slice(0, 8)} columns={[
            { key: 'service_date', label: 'Date' },
            { key: 'date_status', label: 'Type', render: (r) => label(r.date_status) },
            { key: 'routes_spiking', label: 'Routes spiking', num: true },
            { key: 'max_demand_ratio', label: 'Peak vs usual', num: true, render: (r) => `${num(r.max_demand_ratio, 2)}×` },
          ]} />
        </Panel>
      </div>
    </div>
  )
}
