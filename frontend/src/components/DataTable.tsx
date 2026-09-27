/**
 * Tables for API rows, built on DataTables (https://datatables.net, core library only).
 *
 * The props are the same as before CMD-026, so no page changed:
 *
 * - **Local tables** (rows already loaded): DataTables sorts every column; tables with more
 *   than 10 rows also get search and paging.
 * - **Server tables** (`sort` + `onSort` given, e.g. the Data explorer): the API sorts and pages
 *   the whole result, so a header click is passed to `onSort` and DataTables only shows the
 *   page; its own search and paging stay off (the page has filters and a Pager).
 *
 * DataTables' default stylesheet is not loaded; `styles/app.css` ("DataTables") themes the
 * generated markup with our tokens.
 *
 * Cells: sorting and search always use the raw value. Plain columns display escaped text.
 * Columns with a `render` function (links, badges, buttons) are drawn by React, but only for
 * rows DataTables actually shows (`deferRender`), once per row, and reused on every redraw.
 * (The wrapper's own "slots" were not used: they create a React root for every cell on every
 * pass, including sorting and type detection, which stalled a 118-row table and made those
 * columns sort by DOM node instead of value.)
 */

import DT from 'datatables.net'
import DataTableReact from 'datatables.net-react'
import { useContext, useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { UNSAFE_LocationContext, UNSAFE_NavigationContext, UNSAFE_RouteContext } from 'react-router-dom'
import type { Row } from '../api/client'

// Register the core library with the React wrapper (a DataTables call, not a React hook).
const registerLibrary = DataTableReact.use
registerLibrary(DT)

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

/** Tables at or below 10 rows show no search box or pager: everything is already visible. */
const INTERACTIVE_FROM = 11

const escape = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

function fallback(v: unknown): string {
 if (v === null || v === undefined || v === '') return '-'
 if (typeof v === 'boolean') return v ? 'Yes' : 'No'
 return String(v)
}

/** Sort/search value: numbers stay numbers, booleans sort as 0/1, null as ''. */
function raw(v: unknown) {
 if (v === null || v === undefined) return ''
 if (typeof v === 'boolean') return v ? 1 : 0
 return v as string | number
}

interface Cell { div: HTMLDivElement; root: Root }

export function DataTable<R extends Row>({ columns, rows, caption, stale, empty, sort, onSort }: Props<R>) {
 const server = !!onSort
 const interactive = !server && rows.length >= INTERACTIVE_FROM
 const signature = columns.map((c) => `${c.key}:${c.label}`).join('|')

 // DataTables renders cells outside React, so the render functions read the latest props and
 // the router's contexts (for <Link>) from this ref instead of a stale closure.
 const navigation = useContext(UNSAFE_NavigationContext)
 const location = useContext(UNSAFE_LocationContext)
 const route = useContext(UNSAFE_RouteContext)
 const latest = useRef({ columns, navigation, location, route })
 // Layout effects run before the wrapper's (passive) redraw effect, so a redraw sees these props.
 useLayoutEffect(() => { latest.current = { columns, navigation, location, route } })

 // One React root per (row, column) that has been displayed; dropped when the rows change.
 const cells = useRef(new WeakMap<object, Map<number, Cell>>())
 const live = useRef<Cell[]>([])
 useEffect(() => {
  const created = live
  return () => {
   const old = created.current
   created.current = []
   cells.current = new WeakMap()
   // Unmount after DataTables has swapped the nodes out (not during React's commit).
   setTimeout(() => old.forEach((c) => c.root.unmount()), 0)
  }
 }, [rows, signature])

 const dtColumns = useMemo(() => columns.map((c, index) => ({
  data: c.key,
  title: escape(c.label),
  orderable: c.sortable !== false,
  className: [c.num ? 'num' : '', c.wrap ? 'wrap' : ''].join(' ').trim(),
  defaultContent: '',
  render: (v: unknown, type: string, row: R) => {
   if (type !== 'display') return raw(v)
   const col = latest.current.columns[index]
   if (!col?.render) return escape(fallback(v))
   let byColumn = cells.current.get(row)
   if (!byColumn) { byColumn = new Map(); cells.current.set(row, byColumn) }
   const hit = byColumn.get(index)
   if (hit) return hit.div
   const div = document.createElement('div')
   const root = createRoot(div)
   const ctx = latest.current
   root.render(
    <UNSAFE_NavigationContext.Provider value={ctx.navigation}>
     <UNSAFE_LocationContext.Provider value={ctx.location}>
      <UNSAFE_RouteContext.Provider value={ctx.route}>{col.render(row)}</UNSAFE_RouteContext.Provider>
     </UNSAFE_LocationContext.Provider>
    </UNSAFE_NavigationContext.Provider>,
   )
   const cell = { div, root }
   byColumn.set(index, cell)
   live.current.push(cell)
   return div
  },
 // eslint-disable-next-line react-hooks/exhaustive-deps
 })), [signature])

 if (!rows.length) return <div className="table-wrap"><p className="empty">{empty ?? 'No rows match these filters.'}</p></div>

 const sortKey = (sort ?? '').replace(/^-/, '')
 const sortIndex = columns.findIndex((c) => c.key === sortKey)
 const order: { idx: number; dir: 'asc' | 'desc' }[] = server && sortIndex >= 0
  ? [{ idx: sortIndex, dir: sort!.startsWith('-') ? 'desc' : 'asc' }] : []

 /** Server tables: turn DataTables' new order into the API's "-col" / "col" and ask for it. */
 const onOrder = (_e: unknown, _settings: unknown, ordering: { col: number; dir: string }[]) => {
  if (!server || !ordering?.length) return
  const { col, dir } = ordering[0]
  const next = `${dir === 'desc' ? '-' : ''}${columns[col].key}`
  if (next !== sort) onSort!(next)
 }

 return (
  <div className={`table-wrap dt-themed ${stale ? 'stale' : ''}`}>
   <DataTableReact
    key={`${signature}:${server}:${interactive}`}
    className="data"
    data={rows}
    columns={dtColumns}
    onOrder={onOrder}
    options={{
     order,
     paging: interactive,
     searching: interactive,
     info: interactive,
     lengthChange: interactive,
     pageLength: 10,
     lengthMenu: [10, 25, 50, 100],
     deferRender: true,
     autoWidth: false,
     language: {
      search: '',
      searchPlaceholder: 'Search this table…',
      lengthMenu: '_MENU_ rows per page',
      info: '_START_-_END_ of _TOTAL_',
      infoEmpty: 'No rows',
      infoFiltered: '(filtered from _MAX_)',
      zeroRecords: 'No rows match this search.',
      paginate: { first: '«', previous: '‹', next: '›', last: '»' },
     },
    }}
   >
    {caption && <caption className="sr-only">{caption}</caption>}
   </DataTableReact>
  </div>
 )
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
