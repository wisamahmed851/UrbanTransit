import { Siren, Warning, WarningCircle, Info } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { RecommendationsResponse } from '../api/types'
import { Pager } from '../components/DataTable'
import { Reveal } from '../components/motion'
import { Empty, ErrorNotice, Loading, PageHead, Panel, Stats, Status } from '../components/ui'
import { label } from '../lib/format'
import { useApi } from '../lib/useApi'

const PRIORITIES = ['Critical', 'High', 'Medium', 'Low'] as const
const PRIORITY_TONE = { Critical: 'critical', High: 'serious', Medium: 'warning', Low: 'neutral' } as const
const CATEGORY_LABEL: Record<string, string> = {
 CAPACITY: 'Capacity', FREQUENCY: 'Frequency', SCHEDULE: 'Schedule', RELIABILITY: 'Reliability', STOP: 'Stop', ANOMALY: 'Anomaly',
}
const PAGE = 24

/** Route ids link to the route page; stop ids and others are shown as text. */
function Subject({ id }: { id: string }) {
 return /^R\d+$/.test(id) ? <Link to={`/routes/${id}`}>Route {id}</Link> : <span>{/^S\d+$/.test(id) ? `Stop ${id}` : id}</span>
}

export function RecommendationsPage() {
 const [params] = useSearchParams()
 const [priority, setPriority] = useState(params.get('priority') ?? '')
 const [category, setCategory] = useState('')
 const [q, setQ] = useState('')
 const [offset, setOffset] = useState(0)
 const recs = useApi<RecommendationsResponse>('/recommendations', {
  priority: priority || undefined, category: category || undefined, q: q.trim() || undefined, limit: PAGE, offset,
 })
 const s = recs.data?.summary
 const reset = (f: () => void) => { f(); setOffset(0) }

 return (
  <div className="page">
   <PageHead title="Recommendations">
    Service changes proposed by the recommendation engine. Each one names the route or stop, the evidence
    from a year of operations that triggered it, and a priority set by passenger impact and severity. The rules and
    their thresholds are in config/thresholds.yaml.
   </PageHead>

   <Stats items={[
    { label: 'Critical', icon: Siren, value: s?.by_priority.Critical ?? '…', format: String, sub: 'act first' },
    { label: 'High', icon: WarningCircle, value: s?.by_priority.High ?? '…', format: String },
    { label: 'Medium', icon: Warning, value: s?.by_priority.Medium ?? '…', format: String },
    { label: 'Low', icon: Info, value: s?.by_priority.Low ?? '…', format: String, sub: s ? `${s.total} recommendations in all` : undefined },
   ]} />

   <form className="filters" onSubmit={(e) => e.preventDefault()}>
    <label className="field">Priority
     <select value={priority} onChange={(e) => reset(() => setPriority(e.target.value))}>
      <option value="">All</option>{PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
     </select>
    </label>
    <label className="field">Category
     <select value={category} onChange={(e) => reset(() => setCategory(e.target.value))}>
      <option value="">All</option>
      {Object.entries(s?.by_category ?? {}).map(([c, n]) => <option key={c} value={c}>{CATEGORY_LABEL[c] ?? label(c)} ({n})</option>)}
     </select>
    </label>
    <label className="field">Search<input type="search" value={q} placeholder="Route, stop or word…" spellCheck={false}
     onChange={(e) => reset(() => setQ(e.target.value))} /></label>
   </form>

   {recs.error && <ErrorNotice error={recs.error} />}
   {!recs.data ? (recs.loading && <Loading what="recommendations" />) : recs.data.rows.length === 0 ? (
    <Empty>No recommendations match these filters.</Empty>
   ) : (
    <>
     <div className="grid-2" style={{ opacity: recs.loading ? 0.6 : 1 }}>
      {recs.data.rows.map((r) => (
       <Reveal key={r.recommendation_id} as="article" className="panel rec-card">
        <header>
         <h3>{r.action}</h3>
         <Status tone={PRIORITY_TONE[r.priority]}>{r.priority}</Status>
        </header>
        <div className="rec-meta"><Subject id={r.subject_id} /><span>{CATEGORY_LABEL[r.category] ?? r.category}</span><span>{r.recommendation_id}</span></div>
        <p><b>Evidence:</b> {r.evidence}</p>
        {r.estimated_impact && <p className="muted">{r.estimated_impact}</p>}
       </Reveal>
      ))}
     </div>
     <Pager total={recs.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
    </>
   )}

   <Panel title="Where these come from">
    <p className="panel-note" style={{ marginTop: 0 }}>
     The engine reads the analysis tables (persistent overcrowding, demand-supply gap, schedule adherence,
     stop performance, anomalies, route reliability, underused services) and applies fixed rules. No generative
     AI is involved. "Estimated impact" lines are the engine's own estimates. The underlying numbers are on{' '}
     <Link to="/crowding">Crowding and capacity</Link>, <Link to="/delays">Delays</Link> and <Link to="/stops">Stops</Link>.
    </p>
   </Panel>
  </div>
 )
}
