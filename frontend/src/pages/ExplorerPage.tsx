import { useState } from 'react'
import { ApiError, downloadCsv } from '../api/client'
import type { TableInfo } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { DataTable, Pager } from '../components/DataTable'
import { FilterBar, type Filters } from '../components/FilterBar'
import { ErrorNotice, Loading, PageHead, Panel } from '../components/ui'
import { label } from '../lib/format'
import { useApi, useRows } from '../lib/useApi'

export function ExplorerPage() {
  const { can } = useAuth()
  const tables = useApi<{ tables: TableInfo[] }>('/analytics')
  const [name, setName] = useState('route_performance')
  const [filters, setFilters] = useState<Filters>({})
  const [sort, setSort] = useState('')
  const [offset, setOffset] = useState(0)
  const [exportError, setExportError] = useState<ApiError | null>(null)
  const [exporting, setExporting] = useState(false)
  const info = tables.data?.tables.find((t) => t.name === name)
  const rows = useRows(name, { ...filters, sort, offset, limit: 50 })

  const pick = (n: string) => { setName(n); setFilters({}); setSort(''); setOffset(0) }
  const exportCsv = async () => {
    setExporting(true); setExportError(null)
    try { await downloadCsv(name, { ...filters, sort }) } catch (e) { setExportError(e as ApiError) } finally { setExporting(false) }
  }

  return (
    <div className="page">
      <PageHead title="Data explorer">
        Every analysis table behind the dashboards, exactly as the pipeline produced it. Filter, sort by any column, and
        export the matching rows as CSV.
      </PageHead>
      {tables.error && <ErrorNotice error={tables.error} />}

      <form className="filters" onSubmit={(e) => e.preventDefault()}>
        <label className="field">Table
          <select value={name} onChange={(e) => pick(e.target.value)}>
            {(tables.data?.tables ?? [{ name, rows: 0 } as TableInfo]).map((t) => (
              <option key={t.name} value={t.name}>{label(t.name)} ({t.rows.toLocaleString()} rows)</option>
            ))}
          </select>
        </label>
        {can('reports:export') && (
          <button type="button" className="btn" onClick={exportCsv} disabled={exporting}>
            {exporting ? 'Preparing CSV…' : 'Export CSV'}
          </button>
        )}
      </form>

      {info && info.filters.length > 0 && (
        <FilterBar supported={info.filters} value={filters} onChange={(f) => { setFilters(f); setOffset(0) }} />
      )}
      {exportError && <ErrorNotice error={exportError} />}

      <Panel title={label(name)} note={info ? `${info.columns.length} columns. Filters available: ${info.filters.map(label).join(', ') || 'none'}.` : undefined}>
        {rows.error ? <ErrorNotice error={rows.error} /> : !rows.data ? <Loading what="rows" /> : (
          <>
            <DataTable rows={rows.data.rows} stale={rows.loading} sort={sort} onSort={(s) => { setSort(s); setOffset(0) }}
              columns={(info?.columns ?? Object.keys(rows.data.rows[0] ?? {}).map((c) => ({ name: c, type: '' }))).map((c) => ({
                key: c.name, label: c.name, num: /int|double|decimal|bigint/.test(c.type),
              }))} />
            <Pager total={rows.data.total} limit={rows.data.limit} offset={offset} onChange={setOffset} />
          </>
        )}
      </Panel>
    </div>
  )
}
