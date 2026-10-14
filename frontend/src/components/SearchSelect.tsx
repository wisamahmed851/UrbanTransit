/**
 * Searchable picker for a foreign key (e.g. a route's origin stop). Typing searches the
 * referenced table on the server (id or name); the stored value is still the plain id.
 * ARIA combobox: Arrow keys move, Enter picks, Escape closes.
 */

import { useEffect, useId, useRef, useState } from 'react'
import { api, type Row } from '../api/client'

const NAME: Record<string, string> = { stops: 'stop_name', routes: 'route_name', vehicles: 'registration_no' }
const ID: Record<string, string> = { stops: 'stop_id', routes: 'route_id', vehicles: 'vehicle_id' }

interface Page { rows: Row[] }
const label = (table: string, r: Row) => `${r[ID[table]]} - ${r[NAME[table]]}`

export function SearchSelect({ table, value, onChange, invalid }: {
 table: string; value: string; onChange: (id: string) => void; invalid?: boolean
}) {
 const [text, setText] = useState('')
 const [open, setOpen] = useState(false)
 const [options, setOptions] = useState<Row[]>([])
 const [active, setActive] = useState(0)
 const listId = useId()
 const box = useRef<HTMLDivElement>(null)

 // Show "S0001 - Airport" for the current id instead of the bare id.
 useEffect(() => {
  if (!value) { setText(''); return }
  api<{ row: Row }>(`/admin/${table}/${value}`).then((d) => setText(label(table, d.row))).catch(() => setText(value))
 }, [table, value])

 // Debounced server search while the list is open.
 useEffect(() => {
  if (!open) return
  const q = value ? '' : text  // a chosen value shows its label, so list everything
  const t = setTimeout(() => {
   api<Page>(`/admin/${table}`, { query: { q, limit: 20 } }).then((d) => { setOptions(d.rows); setActive(0) }).catch(() => setOptions([]))
  }, 180)
  return () => clearTimeout(t)
 }, [open, text, table, value])

 const pick = (r: Row) => { onChange(String(r[ID[table]])); setText(label(table, r)); setOpen(false) }

 return (
  <div className="combo" ref={box} onBlur={(e) => { if (!box.current?.contains(e.relatedTarget)) setOpen(false) }}>
   <input role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-invalid={invalid}
    placeholder={`Search ${table} by id or name…`} value={text} autoComplete="off"
    onFocus={(e) => { setOpen(true); e.currentTarget.select() }}
    onChange={(e) => { setText(e.target.value); setOpen(true); if (value) onChange('') }}
    onKeyDown={(e) => {
     if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, options.length - 1)) }
     else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
     else if (e.key === 'Enter' && open && options[active]) { e.preventDefault(); pick(options[active]) }
     else if (e.key === 'Escape' && open) { e.stopPropagation(); setOpen(false) }
    }} />
   {open && (
    <ul className="combo-list" id={listId} role="listbox">
     {options.length === 0 && <li className="combo-empty">No matching {table}</li>}
     {options.map((r, i) => (
      <li key={String(r[ID[table]])} role="option" aria-selected={i === active} className={i === active ? 'on' : ''}
       onMouseDown={(e) => e.preventDefault()} onClick={() => pick(r)}>
       <b>{r[ID[table]]}</b> <span>{r[NAME[table]]}</span>
      </li>
     ))}
    </ul>
   )}
  </div>
 )
}
