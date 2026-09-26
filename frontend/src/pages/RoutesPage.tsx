import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, RouteBadge, RouteClass, ScoreBar } from '../components/ui'
import { label, num, pct, ROUTE_CLASSES } from '../lib/format'
import { useRows } from '../lib/useApi'

export function RoutesPage() {
  const perf = useRows('route_performance', { limit: 1000, sort: '-composite_score' })
  const [cls, setCls] = useState('')
  const [type, setType] = useState('')
  const [q, setQ] = useState('')
  const [flaggedOnly, setFlaggedOnly] = useState(false)

  const rows = useMemo(() => (perf.data?.rows ?? []).filter((r) =>
    (!cls || r.route_class === cls) && (!type || r.route_type === type) && (!flaggedOnly || r.overcrowded_flag) &&
    (!q || `${r.route_id} ${r.route_code}`.toLowerCase().includes(q.toLowerCase()))), [perf.data, cls, type, q, flaggedOnly])

  return (
    <div className="page">
      <PageHead title="Routes">
        Every route scored on nine measures: demand, occupancy, punctuality, delay frequency, travel time, reliability,
        passenger load, underuse and overcrowding. The composite decides the class. Select a route for the details.
      </PageHead>
      {perf.error && <ErrorNotice error={perf.error} />}
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Route filters">
        <label className="field">Find a route<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="R097 or BRT1…" /></label>
        <label className="field">Class
          <select value={cls} onChange={(e) => setCls(e.target.value)}>
            <option value="">All classes</option>{ROUTE_CLASSES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="field">Route type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All types</option>{['brt', 'trunk', 'local', 'feeder'].map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        </label>
        <label className="field" style={{ gridAutoFlow: 'column', alignItems: 'center', gap: '0.4rem' }}>
          <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} style={{ minWidth: 0 }} />
          Only persistently overcrowded
        </label>
      </form>
      <Panel title={`${rows.length} routes`}>
        {perf.loading && !perf.data ? <Loading what="routes" /> : (
          <DataTable rows={rows} rowKey={(r) => String(r.route_id)} columns={[
            { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}><RouteBadge code={r.route_code} type={r.route_type} id={r.route_id} /></Link> },
            { key: 'route_type', label: 'Type', render: (r) => label(r.route_type) },
            { key: 'route_class', label: 'Class', render: (r) => <RouteClass value={r.route_class} /> },
            { key: 'composite_score', label: 'Composite score', render: (r) => <ScoreBar value={r.composite_score} /> },
            { key: 'med_daily_boardings', label: 'Boardings / day', num: true, render: (r) => num(r.med_daily_boardings) },
            { key: 'med_punctuality', label: 'On time', num: true, render: (r) => pct(r.med_punctuality) },
            { key: 'med_overload_share', label: 'Trips overloaded', num: true, render: (r) => pct(r.med_overload_share) },
            { key: 'overcrowded_flag', label: 'Overcrowded flag', render: (r) => (r.overcrowded_flag ? 'Yes' : 'No') },
          ]} />
        )}
      </Panel>
    </div>
  )
}
