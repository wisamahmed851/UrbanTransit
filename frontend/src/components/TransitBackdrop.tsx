/**
 * Animated transit-network band behind a page header (CMD-029): octilinear route lines like a
 * metro diagram, stations, and buses that glide between stops, dwell, and move on.
 *
 * Performance (60fps-animation skill): the lines are one static SVG; stations and buses are
 * small HTML elements moved with `transform` only (compositor), positioned in container units
 * (`cqw`), so resizing needs no JavaScript. The band sits above the page's glass panels, never
 * behind them: moving content under `backdrop-filter` would force a re-blur every frame. It
 * pauses (animation-play-state) while scrolled out of view.
 *
 * Reduced motion (accessible-animation skill): buses rest at their stations, the glow holds
 * still; the drawing stays as a static illustration.
 */

import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'

type Kind = 'brt' | 'trunk' | 'local' | 'feeder'

interface Line { kind: Kind; points: [number, number][] }   // x: % of width; y: 0-200, scaled to the band's height
interface Bus { kind: Kind; y: number; from: number; to: number; seconds: number; delay: number }

/** Two layouts so the Overview and the Map page do not look copied. */
const LAYOUTS: Record<'overview' | 'map', { lines: Line[]; buses: Bus[] }> = {
 overview: {
  lines: [
   { kind: 'brt', points: [[-2, 150], [24, 150], [31, 72], [66, 72], [73, 150], [102, 150]] },
   { kind: 'trunk', points: [[-2, 58], [14, 58], [21, 128], [52, 128], [59, 40], [102, 40]] },
   { kind: 'local', points: [[34, 196], [40, 110], [84, 110], [90, 186]] },
   { kind: 'feeder', points: [[78, 16], [84, 72], [102, 72]] },
  ],
  buses: [
   { kind: 'brt', y: 150, from: 0, to: 24, seconds: 9, delay: 0 },
   { kind: 'brt', y: 72, from: 31, to: 66, seconds: 12, delay: -4 },
   { kind: 'brt', y: 150, from: 73, to: 100, seconds: 10, delay: -7 },
   { kind: 'trunk', y: 128, from: 21, to: 52, seconds: 11, delay: -2 },
   { kind: 'trunk', y: 40, from: 59, to: 100, seconds: 14, delay: -9 },
   { kind: 'local', y: 110, from: 40, to: 84, seconds: 15, delay: -5 },
  ],
 },
 map: {
  lines: [
   { kind: 'brt', points: [[-2, 104], [102, 104]] },
   { kind: 'trunk', points: [[8, -4], [20, 104], [36, 196]] },
   { kind: 'trunk', points: [[58, 196], [70, 104], [84, 12], [102, 12]] },
   { kind: 'local', points: [[-2, 40], [46, 40], [54, 104], [62, 160], [102, 160]] },
   { kind: 'feeder', points: [[88, 196], [92, 104]] },
  ],
  buses: [
   { kind: 'brt', y: 104, from: 0, to: 48, seconds: 11, delay: 0 },
   { kind: 'brt', y: 104, from: 52, to: 100, seconds: 12, delay: -6 },
   { kind: 'local', y: 40, from: 0, to: 46, seconds: 13, delay: -3 },
   { kind: 'local', y: 160, from: 62, to: 100, seconds: 12, delay: -8 },
   { kind: 'trunk', y: 12, from: 84, to: 100, seconds: 8, delay: -2 },
  ],
 },
}

/** Every vertex is a station; where two lines share a point it is drawn as a hub. */
function stations(lines: Line[]) {
 const seen = new Map<string, { x: number; y: number; hub: boolean }>()
 for (const l of lines) {
  for (const [x, y] of l.points) {
   if (x < 0 || x > 100 || y < 0 || y > 200) continue
   const key = `${x},${y}`
   const hit = seen.get(key)
   seen.set(key, { x, y, hub: !!hit })
  }
 }
 return [...seen.values()]
}

export function TransitBackdrop({ variant = 'overview' }: { variant?: 'overview' | 'map' }) {
 const ref = useRef<HTMLDivElement>(null)
 const { lines, buses } = LAYOUTS[variant]

 // Stop animating while the band is off screen (CSS animations keep running otherwise).
 useEffect(() => {
  const el = ref.current
  if (!el || !('IntersectionObserver' in window)) return
  const io = new IntersectionObserver(([entry]) => el.classList.toggle('bd-paused', !entry.isIntersecting))
  io.observe(el)
  return () => io.disconnect()
 }, [])

 return (
  <div ref={ref} className="transit-backdrop" aria-hidden="true">
   <i className="bd-glow bd-glow-a" /><i className="bd-glow bd-glow-b" />
   <svg className="bd-lines" viewBox="0 0 100 200" preserveAspectRatio="none">
    {lines.map((l, i) => (
     <polyline key={i} data-kind={l.kind} points={l.points.map((p) => p.join(',')).join(' ')}
      vectorEffect="non-scaling-stroke" fill="none" strokeLinejoin="round" strokeLinecap="round" />
    ))}
   </svg>
   {stations(lines).map((s) => (
    <i key={`${s.x}-${s.y}`} className={`bd-stop ${s.hub ? 'hub' : ''}`} style={{ left: `${s.x}%`, top: `${s.y / 2}%` }} />
   ))}
   {buses.map((b, i) => (
    <i key={i} className="bd-bus" data-kind={b.kind}
     style={{ left: `${b.from}%`, top: `${b.y / 2}%`, '--d': b.to - b.from, '--t': `${b.seconds}s`, '--delay': `${b.delay}s` } as CSSProperties} />
   ))}
  </div>
 )
}

/** A page header with the animated network behind it. */
export function HeroBand({ variant, compact = false, children }: { variant: 'overview' | 'map'; compact?: boolean; children: ReactNode }) {
 return (
  <div className={`hero-band ${compact ? 'compact' : ''}`}>
   <TransitBackdrop variant={variant} />
   <div className="hero-band-content">{children}</div>
  </div>
 )
}
