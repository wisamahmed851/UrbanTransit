import { useState } from 'react'
import type { ComparisonCase, ComparisonResponse, ComparisonTask } from '../api/types'
import { HBarChart } from '../components/charts'
import { DataTable, Pager } from '../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Segmented, Status } from '../components/ui'
import { num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

type Task = ComparisonTask['task']
const STATUS_LABEL: Record<string, string> = {
 BothCorrect: 'Both right', SparkOnlyCorrect: 'Only Spark right', PyOnlyCorrect: 'Only Python right', BothWrong: 'Both wrong',
}
const STATUS_TONE = { BothCorrect: 'good', SparkOnlyCorrect: 'warning', PyOnlyCorrect: 'warning', BothWrong: 'critical' } as const
const PAGE = 50

export function ComparisonPage() {
 const summary = useApi<ComparisonResponse>('/comparison')
 const [task, setTask] = useState<Task>('crowding_flag')
 const [status, setStatus] = useState('')
 const [offset, setOffset] = useState(0)
 const cases = useApi<{ total: number; rows: ComparisonCase[] }>(`/comparison/${task}`, { agreement_status: status || undefined, limit: PAGE, offset })
 const current = summary.data?.tasks.find((t) => t.task === task)
 const numeric = task === 'daily_boardings'

 return (
  <div className="page">
   <PageHead title="Spark vs Python">
    The same unseen test cases (July and August 2026) scored independently by the Spark MLlib models and
    the Python models . Where they agree the answer is more trustworthy; where they disagree the reason is
    usually a difference in features or thresholds, noted per task.
   </PageHead>

   {summary.error && <ErrorNotice error={summary.error} />}
   {!summary.data ? <Loading what="comparison" /> : (
    <div className="grid-3">
     {summary.data.tasks.map((t) => (
      <Panel key={t.task} title={t.title} note={`${t.cases} cases`}>
       <HBarChart name="Rate" format={(v) => pct(v, 0)} height={130} data={[
        { label: 'Agree', value: t.agreement_rate ?? 0 },
        { label: 'Spark right', value: t.spark_correct_rate ?? 0 },
        { label: 'Python right', value: t.python_correct_rate ?? 0 },
       ]} />
       <p className="panel-note">{t.caveat}</p>
      </Panel>
     ))}
    </div>
   )}
   {summary.data && (
    <p className="panel-note">
     Overall agreement across {summary.data.cases.toLocaleString()} cases: <b>{pct(summary.data.overall_agreement_rate, 1)}</b>,
     counted from the cases below. (The report text says "roughly 80%"; the counted rate is lower.)
    </p>
   )}

   <Panel title="Cases" action={<Segmented label="Task" value={task} onChange={(v) => { setTask(v); setOffset(0) }}
    options={[{ value: 'delay_severity', label: 'Delay' }, { value: 'crowding_flag', label: 'Crowding' }, { value: 'daily_boardings', label: 'Demand' }]} />}>
    <form className="filters" onSubmit={(e) => e.preventDefault()}>
     <label className="field">Outcome
      <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0) }}>
       <option value="">All ({current?.cases ?? '…'})</option>
       {Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l} ({current?.by_status[k] ?? 0})</option>)}
      </select>
     </label>
    </form>
    {cases.error ? <ErrorNotice error={cases.error} /> : !cases.data ? <Loading what="cases" /> : (
     <>
      <DataTable rows={cases.data.rows} stale={cases.loading} columns={[
       { key: 'case_id', label: numeric ? 'Route and day' : 'Trip and day' },
       { key: 'actual', label: 'Actual', num: numeric, render: (r) => numeric ? num(Number(r.actual)) : r.actual },
       { key: 'spark_prediction', label: 'Spark', num: numeric, render: (r) => numeric ? num(Number(r.spark_prediction)) : r.spark_prediction },
       { key: 'python_prediction', label: 'Python', num: numeric, render: (r) => numeric ? num(Number(r.python_prediction)) : r.python_prediction },
       ...(numeric ? [{ key: 'absolute_difference', label: 'Spark - Python gap', num: true, render: (r: ComparisonCase) => num(r.absolute_difference) }]
        : [{ key: 'python_value', label: 'Python probability', num: true, render: (r: ComparisonCase) => pct(Number(r.python_value), 0) }]),
       { key: 'agreement_status', label: 'Outcome', render: (r) => <Status tone={STATUS_TONE[r.agreement_status as keyof typeof STATUS_TONE] ?? 'neutral'}>{STATUS_LABEL[r.agreement_status] ?? r.agreement_status}</Status> },
       { key: 'explanation', label: 'Explanation ', wrap: true },
      ]} />
      <Pager total={cases.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
     </>
    )}
   </Panel>
  </div>
 )
}
