import { useState } from 'react'
import { api, ApiError, type Row } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { DataTable, Pager } from '../../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Segmented } from '../../components/ui'
import { useApi } from '../../lib/useApi'

type Entity = 'routes' | 'stops' | 'vehicles'
const KEY: Record<Entity, string> = { routes: 'route_id', stops: 'stop_id', vehicles: 'vehicle_id' }
const LIST_COLUMNS: Record<Entity, string[]> = {
  routes: ['route_id', 'route_code', 'route_name', 'route_type', 'distance_km', 'status'],
  stops: ['stop_id', 'stop_name', 'zone', 'stop_type', 'has_shelter', 'opened_date'],
  vehicles: ['vehicle_id', 'registration_no', 'vehicle_type', 'capacity_total', 'depot', 'status'],
}

interface ListResponse { total: number; limit: number; offset: number; rows: Row[] }

export function ReferencePage() {
  const { can } = useAuth()
  const [entity, setEntity] = useState<Entity>('routes')
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<{ mode: 'create' | 'edit'; row: Row } | null>(null)
  const list = useApi<ListResponse>(`/admin/${entity}`, { q, offset, limit: 50 })
  const writable = can('reference:write')

  const switchTo = (e: Entity) => { setEntity(e); setQ(''); setOffset(0); setEditing(null) }
  const template = (): Row => {
    const sample = list.data?.rows[0] ?? {}
    return Object.fromEntries(Object.entries(sample).filter(([k]) => k !== 'dq_flags')
      .map(([k, v]) => [k, typeof v === 'boolean' ? false : typeof v === 'number' ? null : '']))
  }

  return (
    <div className="page">
      <PageHead title="Routes, stops and vehicles">
        The working copy of the network's reference data. Changes are saved to the app database and recorded in the audit
        log. They do not change the analysis results, which come from the pipeline's own copy.
      </PageHead>

      <div className="filters">
        <Segmented label="Entity" value={entity} onChange={switchTo}
          options={[{ value: 'routes', label: 'Routes' }, { value: 'stops', label: 'Stops' }, { value: 'vehicles', label: 'Vehicles' }]} />
        <label className="field">Search<input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0) }} placeholder="ID or name…" /></label>
        {writable && <button className="btn" type="button" onClick={() => setEditing({ mode: 'create', row: template() })}>Add {entity.slice(0, -1)}</button>}
      </div>

      {editing && (
        <EditForm entity={entity} mode={editing.mode} initial={editing.row}
          onDone={() => { setEditing(null); list.reload() }} onCancel={() => setEditing(null)} />
      )}

      <Panel title={list.data ? `${list.data.total.toLocaleString()} ${entity}` : entity}>
        {list.error ? <ErrorNotice error={list.error} /> : !list.data ? <Loading /> : (
          <>
            <DataTable rows={list.data.rows} stale={list.loading} rowKey={(r) => String(r[KEY[entity]])} columns={[
              ...LIST_COLUMNS[entity].map((c) => ({ key: c, label: c.replace(/_/g, ' ') })),
              { key: 'dq_flags', label: 'Data-quality flags', sortable: false, render: (r) => (Array.isArray(r.dq_flags) && r.dq_flags.length ? r.dq_flags.join(', ') : '-') },
              ...(writable ? [{ key: '_edit', label: '', sortable: false, render: (r: Row) => (
                <button className="btn btn-quiet" type="button" onClick={() => setEditing({ mode: 'edit', row: r })}>Edit</button>) }] : []),
            ]} />
            <Pager total={list.data.total} limit={list.data.limit} offset={offset} onChange={setOffset} />
          </>
        )}
      </Panel>
    </div>
  )
}

function EditForm({ entity, mode, initial, onDone, onCancel }: {
  entity: Entity; mode: 'create' | 'edit'; initial: Row; onDone: () => void; onCancel: () => void
}) {
  const key = KEY[entity]
  const [values, setValues] = useState<Row>(() => Object.fromEntries(Object.entries(initial).filter(([k]) => k !== 'dq_flags')))
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const fieldErrors = (error?.details?.fields ?? {}) as Record<string, string>

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    const body = mode === 'edit' ? Object.fromEntries(Object.entries(values).filter(([k, v]) => k !== key && v !== initial[k])) : values
    try {
      await api(mode === 'edit' ? `/admin/${entity}/${initial[key]}` : `/admin/${entity}`,
        { method: mode === 'edit' ? 'PATCH' : 'POST', body: JSON.stringify(body) })
      onDone()
    } catch (err) { setError(err as ApiError) } finally { setBusy(false) }
  }

  const remove = async () => {
    if (!window.confirm(`Delete ${entity.slice(0, -1)} ${initial[key]}? This cannot be undone.`)) return
    setBusy(true); setError(null)
    try { await api(`/admin/${entity}/${initial[key]}`, { method: 'DELETE' }); onDone() }
    catch (err) { setError(err as ApiError) } finally { setBusy(false) }
  }

  const sample = initial
  return (
    <Panel title={mode === 'edit' ? `Edit ${initial[key]}` : `New ${entity.slice(0, -1)}`}>
      <form onSubmit={save} style={{ display: 'grid', gap: '1rem' }}>
        <div className="filters">
          {Object.keys(values).map((k) => {
            const v = values[k]
            const isBool = typeof sample[k] === 'boolean'
            const isNum = typeof sample[k] === 'number' || (mode === 'create' && sample[k] === null)
            const isDate = /_date$/.test(k)
            return (
              <label className="field" key={k}>{k.replace(/_/g, ' ')}
                {isBool ? (
                  <input type="checkbox" checked={!!v} onChange={(e) => setValues({ ...values, [k]: e.target.checked })} style={{ minWidth: 0 }} />
                ) : (
                  <input type={isDate ? 'date' : isNum ? 'number' : 'text'} step="any" value={v === null ? '' : String(v)}
                    disabled={mode === 'edit' && k === key}
                    onChange={(e) => setValues({ ...values, [k]: isNum ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value })} />
                )}
                {fieldErrors[k] && <span className="field-error">{fieldErrors[k]}</span>}
              </label>
            )
          })}
        </div>
        {error && !Object.keys(fieldErrors).length && <ErrorNotice error={error} />}
        <div className="btn-row">
          <button className="btn" type="submit" disabled={busy}>{mode === 'edit' ? 'Save changes' : `Add ${entity.slice(0, -1)}`}</button>
          <button className="btn btn-quiet" type="button" onClick={onCancel}>Cancel</button>
          {mode === 'edit' && <button className="btn btn-danger" type="button" onClick={remove} disabled={busy}>Delete</button>}
        </div>
      </form>
    </Panel>
  )
}
