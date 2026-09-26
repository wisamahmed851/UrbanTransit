import { useMemo, useState } from 'react'
import type { Row } from '../api/client'
import type { ClustersResponse, MetricRow, MetricsResponse } from '../api/types'
import { DataTable, type Column } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Segmented, Status } from '../components/ui'
import { num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

type Task = 'delay_severity' | 'crowding_flag' | 'daily_boardings' | 'route_clustering'

const TASKS: { value: Task; label: string; about: string; metrics: [string, string][] }[] = [
  { value: 'delay_severity', label: 'Delay severity', about: 'Predicts whether a trip will be on time, or minor, moderate or severely late.',
    metrics: [['accuracy', 'Accuracy'], ['macro_f1', 'Macro F1'], ['weighted_f1', 'Weighted F1']] },
  { value: 'crowding_flag', label: 'Crowding', about: 'Predicts whether a trip will run above 90% of capacity.',
    metrics: [['accuracy', 'Accuracy'], ['macro_f1', 'Macro F1'], ['weighted_f1', 'Weighted F1']] },
  { value: 'daily_boardings', label: 'Daily demand', about: 'Forecasts boardings per route per day from earlier days only.',
    metrics: [['mae', 'MAE'], ['rmse', 'RMSE'], ['r2', 'R²'], ['mape', 'MAPE %']] },
  { value: 'route_clustering', label: 'Route groups', about: 'Groups routes with similar load, demand and reliability.',
    metrics: [['silhouette', 'Silhouette'], ['actual_clusters', 'Clusters found']] },
]

/** Held-out results only: `test` for full runs, `test_full` for sample-trained runs, `train` for clustering. */
const HEADLINE_SPLITS = new Set(['test', 'test_full'])

export function ModelsPage() {
  const [task, setTask] = useState<Task>('delay_severity')
  const metrics = useApi<MetricsResponse>('/models/metrics', { task })
  const clusters = useApi<ClustersResponse>('/models/clusters')
  const spec = TASKS.find((t) => t.value === task)!

  const table = useMemo(() => {
    const byFile = new Map<string, Row>()
    for (const m of (metrics.data?.rows ?? []) as MetricRow[]) {
      const headline = task === 'route_clustering' ? m.split_type === 'train' : HEADLINE_SPLITS.has(m.split_type)
      if (!headline) continue
      const row = byFile.get(m.source_file) ?? {
        source_file: m.source_file, algorithm: m.algorithm, split: m.split_type,
        k: (m.extra_json?.k as number) ?? null, scope: (m.extra_json?.model_scope as string) ?? null,
        validity: m.validity_flag,
      }
      row[m.metric_name] = m.metric_value
      byFile.set(m.source_file, row)
    }
    return [...byFile.values()]
  }, [metrics.data, task])

  const columns: Column[] = [
    { key: 'source_file', label: 'Run', render: (r) => String(r.source_file).replace(/\.json$/, '').replace(`${task}_`, '').replace(/_/g, ' ') },
    ...(task === 'route_clustering' ? [{ key: 'k', label: 'k', num: true } as Column] : []),
    ...spec.metrics.map(([k, l]) => ({
      key: k, label: l, num: true,
      render: (r: Row) => r[k] == null ? '-' : ['accuracy'].includes(k) ? pct(r[k], 1) : Number(r[k]).toFixed(k === 'mae' || k === 'rmse' || k === 'mape' ? 1 : 3),
    } as Column)),
    { key: 'split', label: 'Evaluated on', render: (r) => (r.split === 'test_full' ? 'Full test set (trained on a 10% sample)' : r.split === 'train' ? 'Training-period routes' : 'Held-out test set') },
    { key: 'validity', label: 'Status', render: (r) => r.validity === 'INVALID' ? <Status tone="critical">Not valid</Status> : <Status tone="neutral">Not reviewed for serving</Status> },
  ]

  return (
    <div className="page">
      <PageHead title="Model results">
        Results of the Phase 6 models, as reported by their runs. They are shown for transparency; no model has been
        approved to power predictions yet.
      </PageHead>

      {metrics.data?.warnings.map((w) => (
        <div key={w.task} className="notice notice-error" role="alert">
          <strong>These delay-severity scores do not describe a usable model.</strong>
          <span>Every delay model was trained with the trip's own occupancy as an input, which is only known after the
            trip has run. The scores overstate what a model could predict before departure. Delay predictions stay off
            until the model is retrained without it.</span>
          <span style={{ color: 'var(--ink-muted)' }}>API: {w.message}</span>
        </div>
      ))}

      <Panel title={spec.label} note={spec.about}
        action={<Segmented label="Model" value={task} onChange={setTask} options={TASKS.map((t) => ({ value: t.value, label: t.label }))} />}>
        {metrics.error ? <ErrorNotice error={metrics.error} /> : metrics.loading && !metrics.data ? <Loading what="metrics" /> : (
          <DataTable rows={table} stale={metrics.loading} columns={columns} />
        )}
        <p className="panel-note">Macro F1 weighs every class equally, so it shows how well rare classes such as severe delays are caught. MAE and RMSE are in boardings per day.</p>
      </Panel>

      <Panel title="Route groups (k-means, 4 groups)" note="Average profile of the routes in each group, from the training period.">
        {clusters.error ? <ErrorNotice error={clusters.error} /> : !clusters.data ? <Loading /> : (
          <>
            <DataTable rows={clusters.data.clusters as unknown as Row[]} columns={[
              { key: 'plain_language_label', label: 'Group' },
              { key: 'routes', label: 'Routes', num: true },
              { key: 'avg_daily_boardings', label: 'Boardings / day', num: true, render: (r) => num(r.avg_daily_boardings) },
              { key: 'route_load_factor', label: 'Average load', num: true, render: (r) => pct(r.route_load_factor, 0) },
              { key: 'trip_punctuality_rate', label: 'On time', num: true, render: (r) => pct(r.trip_punctuality_rate, 0) },
              { key: 'route_reliability_delay_min', label: 'Average delay', num: true, render: (r) => `${num(r.route_reliability_delay_min, 1)} min` },
              { key: 'crowding_rate', label: 'Crowded trips', num: true, render: (r) => pct(r.crowding_rate, 0) },
            ]} />
            <p className="panel-note">Which routes belong to each group has not been exported yet, so routes cannot be listed per group.</p>
          </>
        )}
      </Panel>
    </div>
  )
}
