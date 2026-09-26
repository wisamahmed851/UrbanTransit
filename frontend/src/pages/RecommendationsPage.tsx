import { ErrorNotice, Loading, PageHead, Panel, Status } from '../components/ui'
import { useApi } from '../lib/useApi'

const PRIORITY_TONE = { Critical: 'critical', High: 'critical', Medium: 'warning', Low: 'neutral' } as const

export function RecommendationsPage() {
  const recs = useApi<{ total: number; rows: { recommendation_id: string; subject_id: string; category: string; action: string; evidence: string; priority: keyof typeof PRIORITY_TONE; estimated_impact: string }[] }>('/recommendations')

  return (
    <div className="page">
      <PageHead title="Recommendations">
        Evidence-backed operational actions generated from the Phase 9 recommendation engine.
      </PageHead>

      {recs.loading && <Loading what="recommendations" />}
      {recs.error && <ErrorNotice error={recs.error} />}
      {recs.data && !recs.loading && (
        <Panel title={`${recs.data.total} actionable recommendations`}>
          <div className="grid-2">
            {recs.data.rows.map((r) => (
              <article key={r.recommendation_id} className="panel" style={{ display: 'grid', gap: '0.4rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <h3>{r.action}</h3>
                  <Status tone={PRIORITY_TONE[r.priority]}>{r.priority} priority</Status>
                </div>
                <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-2)' }}>{r.category} · {r.subject_id}</p>
                <p style={{ fontSize: 'var(--fs-sm)' }}><b>Evidence:</b> {r.evidence}</p>
                <p style={{ fontSize: 'var(--fs-sm)' }}><b>Expected effect:</b> {r.estimated_impact}</p>
              </article>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}
