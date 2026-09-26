/**
 * Table for API rows. Sorting and paging can run on the server (analytics endpoints) or
 * locally (small, already-loaded lists), chosen by passing `sort`/`onSort` or not.
 */

import { useMemo, useState, type ReactNode } from 'react'
import type { Row } from '../api/client'

export interface Column<R = Row> {
  key: string
  label: string
  num?: boolean
  wrap?: boolean
  render?: (row: R) => ReactNode
  sortable?: boolean
}

interface Props<R> {
  columns: Column<R>[]
  rows: R[]
  caption?: string
  stale?: boolean
  empty?: ReactNode
  /** server-side sort: "-col" or "col"; omit for local sorting */
  sort?: string
  onSort?: (sort: string) => void
  rowKey?: (row: R, i: number) => string
}

export function DataTable<R extends Row>({ columns, rows, caption, stale, empty, sort, onSort, rowKey }: Props<R>) {
  const [localSort, setLocalSort] = useState('')
  const active = onSort ? sort ?? '' : localSort
  const sorted = useMemo(() => {
    if (onSort || !localSort) return rows
    const key = localSort.replace(/^-/, '')
    const dir = localSort.startsWith('-') ? -1 : 1
    return [...rows].sort((a, b) => {
      const x = a[key], y = b[key]
      if (x === y) return 0
      if (x === null || x === undefined) return 1
      if (y === null || y === undefined) return -1
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * dir
    })
  }, [rows, localSort, onSort])

  const toggle = (key: string) => {
    const next = active === key ? `-${key}` : key
    if (onSort) onSort(next)
    else setLocalSort(next)
  }

  if (!rows.length) return <div className="table-wrap"><p className="empty">{empty ?? 'No rows match these filters.'}</p></div>

  return (
    <div className={`table-wrap ${stale ? 'stale' : ''}`}>
      <table className="data">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => {
              const dir = active === c.key ? 'ascending' : active === `-${c.key}` ? 'descending' : undefined
              return (
                <th key={c.key} className={c.num ? 'num' : ''} aria-sort={dir ?? 'none'} scope="col">
                  {c.sortable === false ? c.label : (
                    <button type="button" onClick={() => toggle(c.key)}>
                      {c.label}<span aria-hidden="true">{dir === 'ascending' ? '▲' : dir === 'descending' ? '▼' : ''}</span>
                    </button>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={rowKey ? rowKey(r, i) : i}>
              {columns.map((c) => (
                <td key={c.key} className={[c.num ? 'num' : '', c.wrap ? 'wrap' : ''].join(' ')}>
                  {c.render ? c.render(r) : fallback(r[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function fallback(v: unknown): ReactNode {
  if (v === null || v === undefined || v === '') return '-'
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return String(v)
}

export function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null
  const from = offset + 1, to = Math.min(offset + limit, total)
  return (
    <div className="pager">
      <span>{from.toLocaleString()}-{to.toLocaleString()} of {total.toLocaleString()}</span>
      <button className="btn btn-quiet" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <button className="btn btn-quiet" disabled={to >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </div>
  )
}
