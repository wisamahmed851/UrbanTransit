import { useState } from 'react'
import type { AuditEntry } from '../../api/types'
import { DataTable, Pager } from '../../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel } from '../../components/ui'
import { useApi } from '../../lib/useApi'

const LIMIT = 50

export function AuditPage() {
  const [actor, setActor] = useState('')
  const [action, setAction] = useState('')
  const [offset, setOffset] = useState(0)
  const log = useApi<{ entries: AuditEntry[] }>('/admin/audit-log', { actor, action, offset, limit: LIMIT })
  const entries = log.data?.entries ?? []

  return (
    <div className="page">
      <PageHead title="Audit log">Every sign-in, export and change, newest first.</PageHead>
      <form className="filters" onSubmit={(e) => e.preventDefault()}>
        <label className="field">User<input value={actor} onChange={(e) => { setActor(e.target.value); setOffset(0) }} placeholder="Exact username…" /></label>
        <label className="field">Action
          <select value={action} onChange={(e) => { setAction(e.target.value); setOffset(0) }}>
            <option value="">All actions</option>
            {['auth.login', 'auth.login_failed', 'reports.export', 'users.create', 'users.update',
              'routes.create', 'routes.update', 'routes.delete', 'stops.create', 'stops.update', 'stops.delete',
              'vehicles.create', 'vehicles.update', 'vehicles.delete'].map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
      </form>
      <Panel>
        {log.error ? <ErrorNotice error={log.error} /> : !log.data ? <Loading what="audit log" /> : (
          <>
            <DataTable rows={entries as never} stale={log.loading} empty="Nothing recorded for these filters." columns={[
              { key: 'timestamp', label: 'When (UTC)', render: (r) => String(r.timestamp).replace('T', ' ').slice(0, 19) },
              { key: 'actor', label: 'User' },
              { key: 'action', label: 'Action' },
              { key: 'entity', label: 'On' },
              { key: 'details', label: 'Details', sortable: false, wrap: true, render: (r) => r.details ? (
                <code style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{JSON.stringify(r.details)}</code>) : '-' },
            ]} />
            <Pager total={offset + entries.length + (entries.length === LIMIT ? 1 : 0)} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Panel>
    </div>
  )
}
