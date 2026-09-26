/** Small presentational pieces shared by every page. */

import type { ReactNode } from 'react'
import type { ApiError } from '../api/client'
import { CLASS_TONE } from '../lib/format'

export function PageHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </header>
  )
}

export function Panel({ title, note, action, children, className = '' }: {
  title?: string; note?: ReactNode; action?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <div className="panel-head">
          <div>{title && <h2>{title}</h2>}{note && <p>{note}</p>}</div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Loading({ what = 'data' }: { what?: string }) {
  return <p className="loading" role="status">Loading {what}…</p>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>
}

export function ErrorNotice({ error }: { error: ApiError }) {
  const hint = error.code === 'network_error'
    ? 'The API did not answer. In WSL run: cd /mnt/d/Techwise_2026 && flask run'
    : error.code === 'forbidden' ? 'Your role does not include this. Ask an admin to change your role.'
    : null
  return (
    <div className="notice notice-error" role="alert">
      <strong>{error.message}</strong>
      {hint && <span>{hint}</span>}
    </div>
  )
}

/** Wraps sample (dummy) content. The hatched edge and the sentence travel with the data. */
export function Sample({ reason, children }: { reason: string; children: ReactNode }) {
  return (
    <div className="sample sample-block">
      <span className="sample-tag"><SampleIcon /> Sample data, not pipeline output</span>
      <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-2)' }}>{reason}</p>
      {children}
    </div>
  )
}

function SampleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="1.5" width="13" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4 12 12 4M1.5 8 8 1.5M8 14.5 14.5 8" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

const TONE_ICON: Record<string, ReactNode> = {
  good: <path d="M3.5 8.5 6.5 11.5 12.5 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />,
  warning: <><path d="M8 2 14.5 13.5h-13z" fill="currentColor" /><path d="M8 6.5v3.2M8 11.6v.1" stroke="#15191c" strokeWidth="1.6" strokeLinecap="round" /></>,
  serious: <><circle cx="8" cy="8" r="6.5" fill="currentColor" /><path d="M8 4.5v4.2M8 11.2v.1" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" /></>,
  critical: <><rect x="2" y="2" width="12" height="12" rx="2" transform="rotate(45 8 8)" fill="currentColor" /><path d="M8 5v3.6M8 10.9v.1" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" /></>,
  neutral: <circle cx="8" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="2" />,
}

export function Status({ tone, children }: { tone: keyof typeof TONE_ICON; children: ReactNode }) {
  return (
    <span className="status" data-tone={tone}>
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">{TONE_ICON[tone]}</svg>
      {children}
    </span>
  )
}

export function RouteClass({ value }: { value: unknown }) {
  const v = String(value ?? '')
  return v ? <Status tone={CLASS_TONE[v] ?? 'neutral'}>{v}</Status> : <>–</>
}

/** Route code on a sign plate; the coloured edge encodes route type (the code is always shown). */
export function RouteBadge({ code, type, id }: { code?: unknown; type?: unknown; id?: unknown }) {
  return (
    <span className="route-badge" data-type={String(type ?? '')} title={type ? `${String(type).toUpperCase()} route ${id ?? ''}` : String(id ?? '')}>
      <i aria-hidden="true" /><b>{String(code ?? id ?? '–')}</b>
    </span>
  )
}

export function Stats({ items }: { items: { label: string; value: ReactNode; sub?: ReactNode }[] }) {
  return (
    <div className="stat-strip">
      {items.map((s) => (
        <div className="stat" key={s.label}>
          <span className="stat-value">{s.value}</span>
          <span className="stat-label">{s.label}</span>
          {s.sub && <span className="stat-sub">{s.sub}</span>}
        </div>
      ))}
    </div>
  )
}

export function ScoreBar({ value }: { value: unknown }) {
  const n = Number(value)
  if (value === null || value === undefined || !Number.isFinite(n)) return <>–</>
  return (
    <span className="cell-bar">
      <span aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, n))}%` }} /></span>
      <b style={{ fontVariantNumeric: 'tabular-nums', minWidth: '2.6rem', textAlign: 'right' }}>{n.toFixed(1)}</b>
    </span>
  )
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}
