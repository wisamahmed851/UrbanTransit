/**
 * Charts (Recharts) following the dataviz rules: thin marks with 4px rounded data-ends,
 * hairline recessive axes, a hover tooltip on every mark, a legend for 2+ series, and a
 * table view twin for every chart. Colours come from CSS tokens so dark mode uses its own
 * validated steps.
 */

import { useEffect, useState, type ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { DataTable, type Column } from './DataTable'
import { Segmented } from './ui'

const TOKENS = ['--ink', '--series-1', '--series-2', '--series-3', '--series-4', '--ink-2', '--ink-muted', '--hairline', '--axis', '--surface'] as const
type Palette = Record<(typeof TOKENS)[number], string>

function readPalette(): Palette {
  const cs = getComputedStyle(document.documentElement)
  return Object.fromEntries(TOKENS.map((t) => [t, cs.getPropertyValue(t).trim()])) as Palette
}

/** Current token values; re-read when the OS scheme or the data-theme attribute changes. */
export function usePalette(): Palette {
  const [p, setP] = useState(readPalette)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setP(readPalette())
    mq.addEventListener('change', update)
    const mo = new MutationObserver(update)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => { mq.removeEventListener('change', update); mo.disconnect() }
  }, [])
  return p
}

const SERIES = ['--series-1', '--series-2', '--series-3', '--series-4'] as const

/** Chart with a Chart / Table switch; the table is the accessible twin. */
export function ChartFrame<R extends Record<string, string | number | boolean | null>>({ chart, rows, columns, legend }: {
  chart: ReactNode; rows: R[]; columns: Column<R>[]; legend?: { label: string; slot: number }[]
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const p = usePalette()
  return (
    <div className="chart">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '0.4rem' }}>
        {legend && legend.length > 1 && view === 'chart' ? (
          <div className="chart-legend">
            {legend.map((l) => (
              <span key={l.label} style={{ '--c': p[SERIES[l.slot]] } as React.CSSProperties}><i />{l.label}</span>
            ))}
          </div>
        ) : <span />}
        <Segmented label="View as" value={view} onChange={setView}
          options={[{ value: 'chart', label: 'Chart' }, { value: 'table', label: 'Table' }]} />
      </div>
      {view === 'chart' ? chart : <DataTable rows={rows} columns={columns} />}
    </div>
  )
}

function TooltipBox({ active, payload, label, format, labelFormat }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string
  format: (v: number) => string; labelFormat?: (l: string) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="tooltip">
      <b>{labelFormat ? labelFormat(String(label)) : label}</b>
      {payload.map((s) => (
        <div className="tooltip-row" key={s.name} style={{ '--c': s.color } as React.CSSProperties}>
          <i />{s.name}: <strong>{format(Number(s.value))}</strong>
        </div>
      ))}
    </div>
  )
}

/**
 * Horizontal bars, one series (slot 1): magnitude by a nominal category.
 * Values are printed by a right-hand category axis (same categories, no second value scale),
 * so every bar, including a 0, shows its number.
 */
export function HBarChart({ data, format, name, height }: {
  data: { label: string; value: number }[]; format: (v: number) => string; name: string; height?: number
}) {
  const p = usePalette()
  const h = height ?? Math.max(120, data.length * 30 + 40)
  const byLabel = new Map(data.map((d) => [d.label, d.value]))
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 8 }} barCategoryGap={6}>
        <CartesianGrid horizontal={false} stroke={p['--hairline']} />
        <XAxis type="number" tickFormatter={format} stroke={p['--axis']} tick={{ fill: p['--ink-muted'], fontSize: 12 }} />
        <YAxis yAxisId="names" type="category" dataKey="label" width={170} stroke={p['--axis']} tick={{ fill: p['--ink-2'], fontSize: 12 }} />
        <YAxis yAxisId="values" orientation="right" type="category" dataKey="label" width={64} axisLine={false} tickLine={false}
          tick={{ fill: p['--ink'], fontSize: 12 }} tickFormatter={(l: string) => format(byLabel.get(l) ?? NaN)} />
        <Tooltip cursor={{ fill: p['--hairline'], opacity: 0.5 }} content={<TooltipBox format={format} />} />
        <Bar yAxisId="names" dataKey="value" name={name} fill={p['--series-1']} radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Vertical bars, one series, ordered x (hours, days). */
export function ColumnChart({ data, format, name, xFormat, height = 240 }: {
  data: { label: string; value: number }[]; format: (v: number) => string; name: string
  xFormat?: (l: string) => string; height?: number
}) {
  const p = usePalette()
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 8 }} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={p['--hairline']} />
        <XAxis dataKey="label" tickFormatter={xFormat} stroke={p['--axis']} tick={{ fill: p['--ink-muted'], fontSize: 12 }} />
        <YAxis tickFormatter={format} stroke={p['--axis']} tick={{ fill: p['--ink-muted'], fontSize: 12 }} width={56} />
        <Tooltip cursor={{ fill: p['--hairline'], opacity: 0.5 }} content={<TooltipBox format={format} labelFormat={xFormat} />} />
        <Bar dataKey="value" name={name} fill={p['--series-1']} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Lines over an ordered x axis; up to 3 series on one axis (never a second y-scale). */
export function LinesChart({ data, xKey, series, format, xFormat, height = 260 }: {
  data: Record<string, string | number | null>[]; xKey: string
  series: { key: string; label: string; slot: number }[]
  format: (v: number) => string; xFormat?: (l: string) => string; height?: number
}) {
  const p = usePalette()
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid vertical={false} stroke={p['--hairline']} />
        <XAxis dataKey={xKey} tickFormatter={xFormat} stroke={p['--axis']} tick={{ fill: p['--ink-muted'], fontSize: 12 }} minTickGap={24} />
        <YAxis tickFormatter={format} stroke={p['--axis']} tick={{ fill: p['--ink-muted'], fontSize: 12 }} width={60} />
        <Tooltip cursor={{ stroke: p['--axis'] }} content={<TooltipBox format={format} labelFormat={xFormat} />} />
        {series.map((s) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={p[SERIES[s.slot]]} strokeWidth={2}
            dot={false} activeDot={{ r: 4, stroke: p['--surface'], strokeWidth: 2 }} connectNulls={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
