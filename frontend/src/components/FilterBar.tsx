/**
 * One filter row above everything it scopes. Only the filters the table supports are shown
 * (the API rejects the others, so offering them would only produce errors).
 */

import { DAY_CLASSES, TIME_PERIODS, label } from '../lib/format'

export type Filters = Partial<Record<'route_id' | 'stop_id' | 'direction' | 'day_class' | 'time_period' | 'date_from' | 'date_to', string>>

export function FilterBar({ supported, value, onChange, children }: {
  supported: string[]
  value: Filters
  onChange: (next: Filters) => void
  children?: React.ReactNode
}) {
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...value, [k]: e.target.value || undefined })
  const has = (k: string) => supported.includes(k)

  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filters">
      {has('route_id') && (
        <label className="field">Route
          <input value={value.route_id ?? ''} onChange={set('route_id')} placeholder="e.g. R001…" size={8} />
        </label>
      )}
      {has('stop_id') && (
        <label className="field">Stop
          <input value={value.stop_id ?? ''} onChange={set('stop_id')} placeholder="e.g. S0001…" size={8} />
        </label>
      )}
      {has('direction') && (
        <label className="field">Direction
          <select value={value.direction ?? ''} onChange={set('direction')}>
            <option value="">Both</option><option value="0">Outbound (0)</option><option value="1">Inbound (1)</option>
          </select>
        </label>
      )}
      {has('day_class') && (
        <label className="field">Day
          <select value={value.day_class ?? ''} onChange={set('day_class')}>
            <option value="">All days</option>
            {DAY_CLASSES.map((d) => <option key={d} value={d}>{label(d)}</option>)}
          </select>
        </label>
      )}
      {has('time_period') && (
        <label className="field">Time of day
          <select value={value.time_period ?? ''} onChange={set('time_period')}>
            <option value="">All day</option>
            {TIME_PERIODS.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        </label>
      )}
      {has('date_from') && (
        <label className="field">From
          <input type="date" value={value.date_from ?? ''} onChange={set('date_from')} min="2025-09-01" max="2026-08-31" />
        </label>
      )}
      {has('date_to') && (
        <label className="field">To
          <input type="date" value={value.date_to ?? ''} onChange={set('date_to')} min="2025-09-01" max="2026-08-31" />
        </label>
      )}
      {Object.values(value).some(Boolean) && (
        <button type="button" className="btn btn-quiet" onClick={() => onChange({})}>Clear filters</button>
      )}
      {children}
    </form>
  )
}
