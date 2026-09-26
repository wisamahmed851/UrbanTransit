import { Link } from 'react-router-dom'
import { ErrorNotice, Loading, PageHead, Panel, Sample, Status } from '../components/ui'
import { useApi } from '../lib/useApi'
import { SAMPLE_RECOMMENDATIONS } from '../sample/sampleData'

const PRIORITY_TONE = { High: 'critical', Medium: 'warning', Low: 'neutral' } as const

export function RecommendationsPage() {
  const recs = useApi<unknown>('/recommendations')

  return (
    <div className="page">
      <PageHead title="Recommendations">
        Service changes proposed for each route and time of day. The recommendation engine is part of Phase 7 and is not
        built yet.
      </PageHead>

      <div className="notice notice-info">
        <strong>Available now from the analysis</strong>
        <span>Capacity changes computed from a year of load data (larger vehicle, more trips, fewer trips) are on{' '}
          <Link to="/crowding">Crowding and capacity</Link>. They are analysis results, not reviewed recommendations.</span>
      </div>

      {recs.loading && <Loading what="recommendations" />}
      {recs.error && <ErrorNotice error={recs.error} />}
      {recs.data !== null && !recs.loading && (
        <Panel title="Recommendations"><pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(recs.data, null, 2)}</pre></Panel>
      )}

      {recs.stub && (
        <Sample reason={`The recommendation service answered: "${recs.stub.reason}". These cards show how recommendations will be laid out; the routes and figures are placeholders.`}>
          <div className="grid-2">
            {SAMPLE_RECOMMENDATIONS.map((r) => (
              <article key={r.id} className="panel" style={{ display: 'grid', gap: '0.4rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <h3>{r.action}</h3>
                  <Status tone={PRIORITY_TONE[r.priority]}>{r.priority} priority</Status>
                </div>
                <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-2)' }}>Route {r.route_id}, {r.when}</p>
                <p style={{ fontSize: 'var(--fs-sm)' }}>{r.why}</p>
                <p style={{ fontSize: 'var(--fs-sm)' }}><b>Expected effect:</b> {r.expected_effect}</p>
              </article>
            ))}
          </div>
        </Sample>
      )}
    </div>
  )
}
