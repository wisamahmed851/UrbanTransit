import { useState } from 'react'
import { api, ApiError, StubUnavailable } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { DataTable } from '../components/DataTable'
import { ErrorNotice, PageHead, Panel, Sample, Segmented } from '../components/ui'
import { pct } from '../lib/format'
import { useApi } from '../lib/useApi'
import { sampleCrowdingPrediction, sampleDelayPrediction, type PredictionInput } from '../sample/sampleData'

type Kind = 'delay' | 'crowding'

interface Outcome {
  kind: Kind
  input: PredictionInput
  stubReason?: string
  real?: unknown
}

export function PredictionsPage() {
  const { can } = useAuth()
  const routes = useApi<{ rows: { route_id: string; route_code: string; route_name: string }[] }>(
    can('reference:read') ? '/admin/routes' : null, { limit: 1000 })
  const [kind, setKind] = useState<Kind>('delay')
  const [input, setInput] = useState<PredictionInput>({ route_id: 'R001', service_date: '2026-09-28', hour: 8, direction: 0 })
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const real = await api(`/predictions/${kind}`, { method: 'POST', body: JSON.stringify(input) })
      setOutcome({ kind, input, real })
    } catch (err) {
      if (err instanceof StubUnavailable) setOutcome({ kind, input, stubReason: err.reason })
      else setError(err as ApiError)
    } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <PageHead title="Predictions">
        Ask how a future trip is likely to run. The prediction service is not live yet, so answers on this page are
        sample figures that show how results will be presented.
      </PageHead>

      <Panel title="Trip to predict" action={<Segmented label="Prediction" value={kind} onChange={(k) => { setKind(k); setOutcome(null) }}
        options={[{ value: 'delay', label: 'Delay' }, { value: 'crowding', label: 'Crowding' }]} />}>
        <form className="filters" onSubmit={submit}>
          <label className="field">Route
            {routes.data ? (
              <select value={input.route_id} onChange={(e) => setInput({ ...input, route_id: e.target.value })}>
                {routes.data.rows.map((r) => <option key={r.route_id} value={r.route_id}>{r.route_code} ({r.route_name})</option>)}
              </select>
            ) : <input value={input.route_id} onChange={(e) => setInput({ ...input, route_id: e.target.value })} />}
          </label>
          <label className="field">Date<input type="date" value={input.service_date} onChange={(e) => setInput({ ...input, service_date: e.target.value })} /></label>
          <label className="field">Departure hour
            <select value={input.hour} onChange={(e) => setInput({ ...input, hour: Number(e.target.value) })}>
              {Array.from({ length: 19 }, (_, i) => i + 5).map((h) => <option key={h} value={h}>{h}:00</option>)}
            </select>
          </label>
          <label className="field">Direction
            <select value={input.direction} onChange={(e) => setInput({ ...input, direction: Number(e.target.value) })}>
              <option value={0}>Outbound (0)</option><option value={1}>Inbound (1)</option>
            </select>
          </label>
          <button className="btn" type="submit" disabled={busy}>{busy ? 'Asking…' : `Predict ${kind}`}</button>
        </form>
      </Panel>

      {error && <ErrorNotice error={error} />}
      {outcome?.real !== undefined && (
        <Panel title="Result"><pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(outcome.real, null, 2)}</pre></Panel>
      )}
      {outcome?.stubReason && <SampleResult outcome={outcome} />}
    </div>
  )
}

function SampleResult({ outcome }: { outcome: Outcome }) {
  const { input } = outcome
  const where = `${input.route_id}, ${input.service_date} at ${input.hour}:00, direction ${input.direction}`
  const reason = `The prediction service answered: "${outcome.stubReason}". The figures below are generated for layout only.`

  if (outcome.kind === 'delay') {
    const p = sampleDelayPrediction(input)
    return (
      <Sample reason={reason}>
        <h2 style={{ fontSize: 'var(--fs-lg)' }}>Likely: {p.predicted}</h2>
        <p style={{ color: 'var(--ink-2)', fontSize: 'var(--fs-sm)' }}>{where}</p>
        <DataTable rows={p.probabilities.map((x) => ({ severity: x.severity, probability: x.probability }))} columns={[
          { key: 'severity', label: 'Outcome', sortable: false },
          { key: 'probability', label: 'Chance (sample)', num: true, sortable: false, render: (r) => pct(r.probability, 0) },
        ]} />
      </Sample>
    )
  }
  const c = sampleCrowdingPrediction(input)
  return (
    <Sample reason={reason}>
      <h2 style={{ fontSize: 'var(--fs-lg)' }}>{c.crowded ? 'Likely crowded' : 'Likely not crowded'}</h2>
      <p style={{ color: 'var(--ink-2)', fontSize: 'var(--fs-sm)' }}>{where}</p>
      <DataTable rows={[
        { m: 'Chance of running above 90% of capacity', v: pct(c.crowding_probability, 0) },
        { m: 'Expected load at the busiest stop', v: pct(c.expected_load, 0) },
      ]} columns={[{ key: 'm', label: 'Measure', sortable: false }, { key: 'v', label: 'Sample value', num: true, sortable: false }]} />
    </Sample>
  )
}
