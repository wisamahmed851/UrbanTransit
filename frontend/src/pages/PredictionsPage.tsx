import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { CrowdingPrediction, CrowdingRiskResponse, DelayPrediction } from '../api/types'
import { HBarChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { EstimateTag, ModelCard, Warnings } from '../components/ModelCard'
import { RouteSelect, TripFields } from '../components/TripForm'
import { DEFAULT_TRIP, tomorrow, type TripInput } from '../lib/trip'
import { ErrorNotice, Loading, PageHead, Panel, Segmented, Status } from '../components/ui'
import { label, num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

type Kind = 'crowding' | 'delay'

export function PredictionsPage() {
  const [kind, setKind] = useState<Kind>('crowding')
  const [trip, setTrip] = useState<TripInput>(DEFAULT_TRIP)
  const [answer, setAnswer] = useState<CrowdingPrediction | DelayPrediction | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      setAnswer(await api(`/predictions/${kind}`, { method: 'POST', body: JSON.stringify(trip) }))
    } catch (err) {
      setAnswer(null); setError(err as ApiError)
    } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <PageHead title="Predictions">
        Ask how a future trip is likely to run. Answers come from the saved Python models (Phase 7), trained on
        September 2025 to May 2026 and scored on July and August 2026. Each answer shows what the model was given.
      </PageHead>

      <Panel title="Trip to predict" action={<Segmented label="Prediction" value={kind} onChange={(k) => { setKind(k); setAnswer(null); setError(null) }}
        options={[{ value: 'crowding', label: 'Crowding risk' }, { value: 'delay', label: 'Delay severity' }]} />}>
        <form className="filters" onSubmit={submit}>
          <TripFields value={trip} onChange={setTrip} />
          <button className="btn" type="submit" disabled={busy}>{busy ? 'Predicting…' : kind === 'crowding' ? 'Predict crowding' : 'Predict delay'}</button>
        </form>
      </Panel>

      {error && <ErrorNotice error={error} />}
      {error?.code === 'no_scheduled_service' && Array.isArray(error.details?.hours_with_service) && (
        <p className="panel-note">Hours with service: {(error.details.hours_with_service as number[]).map((h) => `${String(h).padStart(2, '0')}:00`).join(', ')}</p>
      )}
      {answer?.task === 'crowding_flag' && <CrowdingAnswer a={answer} />}
      {answer?.task === 'delay_severity' && <DelayAnswer a={answer} />}

      <RiskList />
    </div>
  )
}

function where(a: CrowdingPrediction | DelayPrediction) {
  const t = a.trip
  return `Route ${t.route_id}, direction ${t.direction}, ${t.service_date} (${t.day_type}) at ${String(t.hour).padStart(2, '0')}:00`
}

function CrowdingAnswer({ a }: { a: CrowdingPrediction }) {
  const p = a.prediction
  return (
    <Panel>
      <div className="answer">
        <div className="answer-head">
          <div>
            <h3>{p.crowded ? 'Likely crowded' : 'Likely not crowded'}</h3>
            <p className="muted">{where(a)}</p>
          </div>
          <EstimateTag />
        </div>
        <div>
          <div className="meter" role="img" aria-label={`Crowding probability ${pct(p.probability, 0)}, threshold ${pct(p.threshold, 0)}`}>
            <i style={{ width: `${p.probability * 100}%` }} /><b style={{ left: `${p.threshold * 100}%` }} />
          </div>
          <div className="meter-scale"><span>Chance of crowding: <b>{pct(p.probability, 1)}</b></span><span>Flagged at {pct(p.threshold, 0)} or more</span></div>
          <p className="panel-note">{p.meaning}.</p>
        </div>
        <Warnings items={a.warnings} />
        <Context a={a} />
        <ModelCard model={a.model} />
      </div>
    </Panel>
  )
}

function DelayAnswer({ a }: { a: DelayPrediction }) {
  const p = a.prediction
  return (
    <Panel>
      <div className="answer">
        <div className="answer-head">
          <div>
            <h3>Most likely: {p.severity}</h3>
            <p className="muted">{where(a)}</p>
          </div>
          <EstimateTag />
        </div>
        <Warnings items={a.warnings} />
        <HBarChart name="Chance" format={(v) => pct(v, 0)} height={150}
          data={p.probabilities.map((x) => ({ label: x.severity, value: x.probability }))} />
        <p className="panel-note">Bands: {p.bands}.</p>
        <Context a={a} />
        <ModelCard model={a.model} />
      </div>
    </Panel>
  )
}

/** The model's inputs next to what was actually observed for this route, direction and hour. */
function Context({ a }: { a: CrowdingPrediction | DelayPrediction }) {
  const o = a.observed
  return (
    <div className="grid-2">
      <div>
        <h4 className="muted">What the model was given</h4>
        <DataTable rows={Object.entries(a.inputs).map(([k, v]) => ({ input: label(k), value: typeof v === 'number' ? num(v, Number.isInteger(v) ? 0 : 2) : String(v ?? '-') }))}
          columns={[{ key: 'input', label: 'Input', sortable: false }, { key: 'value', label: 'Value', num: true, sortable: false }]} />
      </div>
      <div>
        <h4 className="muted">What was observed ({o.window}, {o.trips} trips)</h4>
        <DataTable rows={[
          { m: 'Trips that were crowded', v: pct(o.crowded_trip_share, 0) },
          { m: 'Average occupancy at the busiest point', v: pct(o.mean_occupancy, 0) },
          { m: 'Occupancy on the busiest 10% of trips', v: pct(o.p90_occupancy, 0) },
          { m: 'Boardings per trip', v: num(o.mean_boardings, 0) },
          { m: 'Average delay', v: o.mean_delay_min == null ? '-' : `${num(o.mean_delay_min, 1)} min` },
        ]} columns={[{ key: 'm', label: 'Measure', sortable: false }, { key: 'v', label: 'Observed', num: true, sortable: false }]} />
      </div>
    </div>
  )
}

/** SRS step 26: every route, direction and hour scored for a chosen day; high-risk trips flagged. */
function RiskList() {
  const [day, setDay] = useState(tomorrow())
  const [route, setRoute] = useState('')
  const risk = useApi<CrowdingRiskResponse>('/predictions/crowding-risk', { date: day, route_id: route || undefined, limit: 40 })
  const d = risk.data
  return (
    <Panel title="High-risk trips" note="Every route, direction and departure hour that runs on this type of day, scored by the crowding model. Highest risk first."
      action={<EstimateTag />}>
      <form className="filters" onSubmit={(e) => e.preventDefault()}>
        <label className="field">Day<input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
        <label className="field">Route<RouteSelect value={route} onChange={setRoute} allowAll /></label>
      </form>
      {risk.error ? <ErrorNotice error={risk.error} /> : !d ? <Loading what="risk scores" /> : (
        <>
          <p className="panel-note" style={{ marginTop: 0 }}>
            {d.flagged.toLocaleString()} of {d.cells.toLocaleString()} {d.day_type} route-hours flagged (chance {pct(d.threshold, 0)} or more).
          </p>
          <DataTable rows={d.rows} stale={risk.loading} columns={[
            { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}>{r.route_id}</Link> },
            { key: 'direction', label: 'Dir.', num: true },
            { key: 'hour', label: 'Departs', num: true, render: (r) => `${String(r.hour).padStart(2, '0')}:00` },
            { key: 'probability', label: 'Chance of crowding', num: true, render: (r) => pct(r.probability, 0) },
            { key: 'flagged', label: 'Flag', render: (r) => r.flagged ? <Status tone="critical">High risk</Status> : <Status tone="neutral">Below threshold</Status> },
            { key: 'observed_crowded_share', label: 'Crowded before', num: true, render: (r) => pct(r.observed_crowded_share, 0) },
            { key: 'observed_mean_occupancy', label: 'Average occupancy', num: true, render: (r) => pct(r.observed_mean_occupancy, 0) },
          ]} />
          <p className="panel-note">"Crowded before" and "Average occupancy" are observed over the last 8 weeks of data, for comparison with the model's estimate.</p>
        </>
      )}
    </Panel>
  )
}
