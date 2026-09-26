import { useMemo, useState } from 'react'
import type { Row } from '../api/client'
import { ChartFrame, HBarChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel } from '../components/ui'
import { label, num } from '../lib/format'
import { useRows } from '../lib/useApi'

export function StopsPage() {
  const stops = useRows('stop_performance', { limit: 1000, sort: '-est_turnover_per_day' })
  const [q, setQ] = useState('')
  const [zone, setZone] = useState('')
  const [bottleneckOnly, setBottleneckOnly] = useState(false)

  const all = useMemo(() => stops.data?.rows ?? [], [stops.data])
  const rows = useMemo(() => all.filter((r) =>
    (!zone || r.zone === zone) && (!bottleneckOnly || r.is_bottleneck) &&
    (!q || `${r.stop_id} ${r.stop_name}`.toLowerCase().includes(q.toLowerCase()))), [all, zone, q, bottleneckOnly])
  const busiest = all.slice(0, 12).map((r) => ({ label: String(r.stop_name), value: Number(r.est_turnover_per_day) }))

  return (
    <div className="page">
      <PageHead title="Stops">
        Stop activity comes from smart-card taps, about 3 to 4% of riders, scaled up by route, month and time of day to
        estimate all riders. Treat small stops' figures as approximate.
      </PageHead>
      {stops.error && <ErrorNotice error={stops.error} />}

      <Panel title="Busiest stops" note="Estimated boardings plus alightings per day the stop was open.">
        {stops.loading && !stops.data ? <Loading /> : (
          <ChartFrame chart={<HBarChart name="Passengers per day" data={busiest} format={(v) => num(v)} />}
            rows={busiest as unknown as Row[]}
            columns={[{ key: 'label', label: 'Stop' }, { key: 'value', label: 'Passengers per day', num: true, render: (r) => num(r.value) }]} />
        )}
      </Panel>

      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Stop filters">
        <label className="field">Find a stop<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or S0001" /></label>
        <label className="field">Fare zone
          <select value={zone} onChange={(e) => setZone(e.target.value)}>
            <option value="">All zones</option><option value="A">A (centre)</option><option value="B">B</option><option value="C">C (outer)</option>
          </select>
        </label>
        <label className="field" style={{ gridAutoFlow: 'column', alignItems: 'center', gap: '0.4rem' }}>
          <input type="checkbox" checked={bottleneckOnly} onChange={(e) => setBottleneckOnly(e.target.checked)} style={{ minWidth: 0 }} />
          Only delay bottlenecks
        </label>
      </form>

      <Panel title={`${rows.length} stops`}>
        <DataTable rows={rows} rowKey={(r) => String(r.stop_id)} columns={[
          { key: 'stop_name', label: 'Stop', render: (r) => `${r.stop_name} (${r.stop_id})` },
          { key: 'zone', label: 'Zone' },
          { key: 'stop_type', label: 'Type', render: (r) => label(r.stop_type) },
          { key: 'est_boardings_per_day', label: 'Boardings / day', num: true, render: (r) => num(r.est_boardings_per_day) },
          { key: 'est_alightings_per_day', label: 'Alightings / day', num: true, render: (r) => num(r.est_alightings_per_day) },
          { key: 'routes_serving', label: 'Routes', num: true },
          { key: 'trips_serving_per_day', label: 'Buses / day', num: true, render: (r) => num(r.trips_serving_per_day) },
          { key: 'late_record_rate', label: 'Late records per bus', num: true, render: (r) => num(r.late_record_rate, 3) },
          { key: 'is_bottleneck', label: 'Bottleneck', render: (r) => (r.is_bottleneck ? 'Yes' : 'No') },
        ]} />
      </Panel>
    </div>
  )
}

