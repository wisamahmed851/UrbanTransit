/** Small presentational pieces shared by every page. */

import { CheckCircle, Circle, Placeholder, Warning, WarningCircle, WarningDiamond } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import type { ApiError } from '../api/client'
import { CLASS_TONE } from '../lib/format'
import { CountUp, Reveal } from './motion'

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
    <Reveal as="section" className={`panel ${className}`}>
      {(title || action) && (
        <div className="panel-head">
          <div>{title && <h2>{title}</h2>}{note && <p>{note}</p>}</div>
          {action}
        </div>
      )}
      {children}
    </Reveal>
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
      <span className="sample-tag"><Placeholder size={14} weight="bold" aria-hidden="true" /> Sample data, not pipeline output</span>
      <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-2)' }}>{reason}</p>
      {children}
    </div>
  )
}

/** Status tone -> Phosphor glyph. Shapes differ per tone, so colour never carries meaning alone. */
const TONE_ICON: Record<'good' | 'warning' | 'serious' | 'critical' | 'neutral', Icon> = {
  good: CheckCircle,
  warning: Warning,
  serious: WarningCircle,
  critical: WarningDiamond,
  neutral: Circle,
}

export function Status({ tone, children }: { tone: keyof typeof TONE_ICON; children: ReactNode }) {
  const Glyph = TONE_ICON[tone]
  return (
    <span className="status" data-tone={tone}>
      <Glyph size={16} weight="fill" aria-hidden="true" />
      {children}
    </span>
  )
}

export function RouteClass({ value }: { value: unknown }) {
  const v = String(value ?? '')
  return v ? <Status tone={CLASS_TONE[v] ?? 'neutral'}>{v}</Status> : <>-</>
}

/** Route code on a sign plate; the coloured edge encodes route type (the code is always shown). */
export function RouteBadge({ code, type, id }: { code?: unknown; type?: unknown; id?: unknown }) {
  return (
    <span className="route-badge" data-type={String(type ?? '')} title={type ? `${String(type).toUpperCase()} route ${id ?? ''}` : String(id ?? '')}>
      <i aria-hidden="true" /><b>{String(code ?? id ?? '-')}</b>
    </span>
  )
}

export interface StatItem {
  label: string
  /** A number counts up (give `format`); any other node is shown as is. */
  value: ReactNode | number
  format?: (n: number) => string
  sub?: ReactNode
  icon?: Icon
  /** Optional trend of real values, drawn as a small sparkline under the number. */
  spark?: number[]
}

/** Floating KPI cards: icon + value + label + context line, optionally a sparkline. */
export function Stats({ items }: { items: StatItem[] }) {
  return (
    <div className="stat-strip">
      {items.map((s) => {
        const Glyph = s.icon
        return (
          <Reveal className="stat" key={s.label}>
            <span className="stat-top">
              <span className="stat-label">{s.label}</span>
              {Glyph && <span className="stat-icon" aria-hidden="true"><Glyph size={18} weight="duotone" /></span>}
            </span>
            <span className="stat-value">
              {typeof s.value === 'number' && s.format ? <CountUp value={s.value} format={s.format} /> : s.value}
            </span>
            {s.sub && <span className="stat-sub">{s.sub}</span>}
            {s.spark && s.spark.length > 1 && <Sparkline values={s.spark} />}
          </Reveal>
        )
      })}
    </div>
  )
}

/** Data-driven sparkline (not decoration): the line is the series itself, min to max. */
function Sparkline({ values }: { values: number[] }) {
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${30 - ((v - min) / span) * 26 - 2}`).join(' ')
  return (
    <svg className="stat-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function ScoreBar({ value }: { value: unknown }) {
  const n = Number(value)
  if (value === null || value === undefined || !Number.isFinite(n)) return <>-</>
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
