import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Row } from '../api/client'
import type { ClustersResponse, MetricRowWithPipeline, MetricsResponse, ModelVersionRow, PythonCluster } from '../api/types'
import { DataTable, type Column } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Segmented, Status } from '../components/ui'
import { num, pct } from '../lib/format'
import { useApi, type ApiState } from '../lib/useApi'

type Task = 'delay_severity' | 'crowding_flag' | 'occupancy_forecast' | 'daily_boardings' | 'stop_period_demand' | 'route_clustering'
type Pipeline = 'python' | 'spark'

const TASKS: { value: Task; label: string; about: string; metrics: [string, string][] }[] = [
 { value: 'crowding_flag', label: 'Crowding', about: 'Predicts whether a trip will run above 90% of capacity.',
  metrics: [['accuracy', 'Accuracy'], ['macro_f1', 'Macro F1'], ['weighted_f1', 'Weighted F1']] },
 { value: 'occupancy_forecast', label: 'Occupancy', about: 'Estimates peak on-board occupancy as a share of assigned capacity using schedule and prior-route history only.',
  metrics: [['mae', 'MAE'], ['rmse', 'RMSE'], ['r2', 'R²'], ['mape_nonzero_pct', 'MAPE above 1%']] },
 { value: 'delay_severity', label: 'Delay severity', about: 'Four generated-data labels: On Time (<5 min), Minor (5–10), Moderate (10–20), or Severe (20+). Major is not a generated class.',
  metrics: [['accuracy', 'Accuracy'], ['macro_f1', 'Macro F1'], ['weighted_f1', 'Weighted F1']] },
 { value: 'daily_boardings', label: 'Daily demand', about: 'Forecasts boardings per route per day from earlier days only.',
  metrics: [['mae', 'MAE'], ['rmse', 'RMSE'], ['r2', 'R²'], ['mape', 'MAPE %']] },
 { value: 'stop_period_demand', label: 'Stop-period demand', about: 'Forecasts ticket tap-ins at one stop and service period; cash riders are not represented.',
  metrics: [['mae', 'MAE'], ['rmse', 'RMSE'], ['r2', 'R²'], ['mape_nonzero_pct', 'MAPE above zero']] },
 { value: 'route_clustering', label: 'Route groups', about: 'Groups routes with similar load, demand and reliability.',
  metrics: [['silhouette', 'Silhouette'], ['actual_clusters', 'Clusters found'], ['clusters', 'Clusters']] },
]

/** SRS 1.7 NFR 4 for classifiers. */
const TARGET = { accuracy: 0.85, macro_f1: 0.8 }
/** Held-out results only: `test` for full runs, `test_full` for sample-trained runs, `train` for clustering. */
const HEADLINE_SPLITS = new Set(['test', 'test_full'])
const CLASSIFIERS = new Set<Task>(['delay_severity', 'crowding_flag'])

export function ModelsPage() {
 const [task, setTask] = useState<Task>('crowding_flag')
 const [pipeline, setPipeline] = useState<Pipeline>('python')
 const metrics = useApi<MetricsResponse>('/models/metrics', { task, pipeline })
 const versions = useApi<{ rows: ModelVersionRow[] }>('/models/versions')
 const spec = TASKS.find((t) => t.value === task)!
 const served = versions.data?.rows.find((v) => v.task === task)

 const table = useMemo(() => {
  const byFile = new Map<string, Row>()
  for (const m of (metrics.data?.rows ?? []) as MetricRowWithPipeline[]) {
   const headline = task === 'route_clustering' ? m.split_type === 'train' : HEADLINE_SPLITS.has(m.split_type)
   if (!headline) continue
   const row = byFile.get(m.source_file) ?? {
    source_file: m.source_file, algorithm: m.algorithm, split: m.split_type,
    k: (m.extra_json?.k as number) ?? null, validity: m.validity_flag,
   }
   row[m.metric_name] = m.metric_value
   byFile.set(m.source_file, row)
  }
  return [...byFile.values()].filter((r) => spec.metrics.some(([k]) => r[k] != null))
 }, [metrics.data, task, spec])

 const isServed = (r: Row) => pipeline === 'python' && served && r.algorithm === served.algorithm
 const columns: Column[] = [
  { key: 'source_file', label: 'Run', render: (r) => (
   <>{String(r.source_file).replace(/\.json$/, '').replace(`${task}_`, '').replace(/_/g, ' ')}{isServed(r) && <> <Status tone="good">Served</Status></>}</>
  ) },
  ...spec.metrics.filter(([k]) => table.some((r) => r[k] != null)).map(([k, l]) => ({
   key: k, label: l, num: true,
   render: (r: Row) => r[k] == null ? '-' : k === 'accuracy' ? pct(r[k], 1) : Number(r[k]).toFixed(['mae', 'rmse', 'mape'].includes(k) ? 1 : 3),
  } as Column)),
  { key: 'split', label: 'Evaluated on', render: (r) => (r.split === 'test_full' ? 'Full test set (trained on a 10% sample)' : r.split === 'train' ? 'Training-period routes' : 'Held-out test set') },
  CLASSIFIERS.has(task)
   ? { key: 'validity', label: 'SRS target', render: (r) => r.validity === 'INVALID' ? <Status tone="critical">Not valid (leakage)</Status>
     : Number(r.accuracy) >= TARGET.accuracy || Number(r.macro_f1) >= TARGET.macro_f1 ? <Status tone="good">Met</Status> : <Status tone="serious">Not met</Status> }
   : { key: 'validity', label: 'Status', render: () => <Status tone="neutral">-</Status> },
 ]

 return (
  <div className="page">
   <PageHead title="Model results">
    Held-out results of both pipelines: Spark MLlib and Python . The Python models marked
    "Served" answer the Predictions, Forecast and What-if pages. Their files were re-scored on this server and
    reproduce the recorded numbers.
   </PageHead>

   {pipeline === 'spark' && metrics.data?.warnings.map((w) => (
    <div key={w.task} className="notice notice-error" role="alert">
     <strong>Some historical Spark delay-severity scores do not describe a usable model.</strong>
     <span>Those runs used the trip's own occupancy as an input, which is only known after the trip has run, so their
      scores overstate what could be predicted before departure. A separately listed Spark retrain is valid only
      when its recorded feature vector excludes occupancy.</span>
     <span style={{ color: 'var(--ink-muted)' }}>API: {w.message}</span>
    </div>
   ))}

   <ServedModels versions={versions} />

   <Panel title={spec.label} note={spec.about}
    action={<div className="filters">
     <Segmented label="Pipeline" value={pipeline} onChange={setPipeline} options={[{ value: 'python', label: 'Python' }, { value: 'spark', label: 'Spark' }]} />
     <Segmented label="Model" value={task} onChange={setTask} options={TASKS.map((t) => ({ value: t.value, label: t.label }))} />
    </div>}>
    {metrics.error ? <ErrorNotice error={metrics.error} /> : metrics.loading && !metrics.data ? <Loading what="metrics" /> : (
     <DataTable rows={table} stale={metrics.loading} columns={columns} />
    )}
    <p className="panel-note">SRS target for classifiers: test accuracy of at least 85% or macro F1 of at least 0.80. Macro F1 weighs every class
     equally, so it shows how well rare classes (severe delays, crowded trips) are caught. MAE and RMSE are boardings per route-day.</p>
   </Panel>

   <PythonClusters />
   <SparkClusters />
  </div>
 )
}

function ServedModels({ versions }: { versions: ApiState<{ rows: ModelVersionRow[] }> }) {
 if (versions.error) return <ErrorNotice error={versions.error} />
 if (!versions.data) return <Loading what="model registry" />
 const rows = versions.data.rows.map((v) => {
  const t = v.metrics.test ?? {}
  const target = v.metrics.srs_target ?? {}
  const met = 'met' in target ? target.met : target.accuracy_met || target.macro_f1_met
  return {
   task: v.task, model: `${v.algorithm} ${v.version}`,
   score: t.accuracy != null ? `accuracy ${pct(t.accuracy, 1)}, macro F1 ${Number(t.macro_f1).toFixed(3)}`
    : t.mae != null ? `MAE ${num(t.mae, 1)} (baseline ${num(Number(target.baseline_test_mae), 1)})`
    : v.metrics.silhouette != null ? `silhouette ${Number(v.metrics.silhouette).toFixed(3)}` : '-',
   target: v.task === 'route_clustering' ? 'n/a' : met ? 'met' : 'not met',
   verified: String(v.metrics.verified_on_this_machine ?? (v.metrics.labels_identical_to_saved_model ? 'PASS' : '-')),
  }
 })
 return (
  <Panel title="Served models" note="The model registry: which saved model answers each task, with its score on unseen data (re-scored on this server).">
   <DataTable rows={rows} columns={[
    { key: 'task', label: 'Task' },
    { key: 'model', label: 'Model' },
    { key: 'score', label: 'Test score' },
    { key: 'target', label: 'SRS target', render: (r) => r.target === 'met' ? <Status tone="good">Met</Status> : r.target === 'not met' ? <Status tone="serious">Not met</Status> : <Status tone="neutral">n/a</Status> },
    { key: 'verified', label: 'Re-scored here', render: (r) => r.verified === 'PASS' ? <Status tone="good">Reproduced</Status> : r.verified },
   ]} />
  </Panel>
 )
}

function PythonClusters() {
 const c = useApi<{ algorithm: string; clusters: PythonCluster[] }>('/models/clusters/python')
 return (
  <Panel title="Route groups (Python, agglomerative, 5 groups)" note="The served clustering model. Average profile of each group over the training period, and its routes.">
   {c.error ? <ErrorNotice error={c.error} /> : !c.data ? <Loading /> : (
    <DataTable rows={c.data.clusters.map((g) => ({ ...g, route_ids: g.route_ids.join(' ') })) as unknown as Row[]} columns={[
     { key: 'profile_label', label: 'Group' },
     { key: 'routes', label: 'Routes', num: true },
     { key: 'avg_daily_boardings', label: 'Boardings / day', num: true, render: (r) => num(r.avg_daily_boardings) },
     { key: 'avg_occupancy', label: 'Average load', num: true, render: (r) => pct(r.avg_occupancy, 0) },
     { key: 'reliability_score', label: 'Trips under 5 min late', num: true, render: (r) => pct(r.reliability_score, 0) },
     { key: 'avg_delay_minutes', label: 'Average delay', num: true, render: (r) => `${num(r.avg_delay_minutes, 1)} min` },
     { key: 'route_ids', label: 'Routes in the group', wrap: true, sortable: false, render: (r) => (
      <div style={{ minWidth: '14rem', maxWidth: '24rem', whiteSpace: 'normal', lineHeight: 1.7 }}>
       {String(r.route_ids).split(' ').map((id, i) => <span key={id}>{i > 0 && ' '}<Link to={`/routes/${id}`}>{id}</Link></span>)}
      </div>
     ) },
    ]} />
   )}
  </Panel>
 )
}

function SparkClusters() {
 const clusters = useApi<ClustersResponse>('/models/clusters')
 return (
  <Panel title="Route groups (Spark, k-means, 4 groups)" note="Average profile of the routes in each group, from the training period.">
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
     <p className="panel-note">The Spark run did not export which routes belong to each group; the Python groups above list them.</p>
    </>
   )}
  </Panel>
 )
}
