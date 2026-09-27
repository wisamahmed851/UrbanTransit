import { useState } from 'react'
import type { JobRun } from '../../api/types'
import { DataTable, Pager } from '../../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Status } from '../../components/ui'
import { useApi } from '../../lib/useApi'

const LIMIT = 50

function duration(value: number | null): string {
 if (value == null) return '—'
 if (value < 60) return `${value.toFixed(1)} s`
 const minutes = Math.floor(value / 60)
 return `${minutes}m ${(value - minutes * 60).toFixed(0)}s`
}

export function JobRunsPage() {
 const [status, setStatus] = useState('')
 const [offset, setOffset] = useState(0)
 const jobs = useApi<{ entries: JobRun[]; total: number }>('/jobs', { status, offset, limit: LIMIT })
 const entries = jobs.data?.entries ?? []

 return (
  <div className="page">
   <PageHead title="Spark job monitor">Recorded pipeline and loader runs. Status comes from the runner, never from a guessed completion.</PageHead>
   <form className="filters" onSubmit={(event) => event.preventDefault()}>
    <label className="field">Status
     <select value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0) }}>
      <option value="">All runs</option>
      <option value="running">Running</option>
      <option value="success">Succeeded</option>
      <option value="failed">Failed</option>
     </select>
    </label>
   </form>
   <Panel title="Job history" note="Use the tracked runner for new Spark work so its log and lifecycle appear here.">
    {jobs.error ? <ErrorNotice error={jobs.error} /> : !jobs.data ? <Loading what="job history" /> : (
     <>
      <DataTable rows={entries as never} stale={jobs.loading} empty="No job runs match this filter." columns={[
       { key: 'job_name', label: 'Job' },
       { key: 'status', label: 'Status', render: (row) => {
        const value = String(row.status)
        return <Status tone={value === 'success' ? 'good' : value === 'failed' ? 'critical' : 'warning'}>{value}</Status>
       } },
       { key: 'started_at', label: 'Started (UTC)', render: (row) => String(row.started_at).replace('T', ' ').slice(0, 19) },
       { key: 'finished_at', label: 'Finished (UTC)', render: (row) => row.finished_at ? String(row.finished_at).replace('T', ' ').slice(0, 19) : 'In progress' },
       { key: 'duration_seconds', label: 'Duration', render: (row) => duration(row.duration_seconds as number | null) },
       { key: 'log_path', label: 'Log', sortable: false, wrap: true, render: (row) => row.log_path ? <code>{String(row.log_path)}</code> : '—' },
      ]} />
      <Pager total={jobs.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
     </>
    )}
   </Panel>
  </div>
 )
}
