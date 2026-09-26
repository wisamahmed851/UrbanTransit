/**
 * Motion building blocks (Motion, formerly Framer Motion). Every animation here has a job:
 *
 * - <Reveal>: cards and charts fade and rise into view once, in reading order (hierarchy).
 *   Uses Motion's `whileInView` (IntersectionObserver); no scroll listeners.
 * - <CountUp>: KPI values tick up to their number when first shown (draws the eye to the KPIs).
 *
 * Both render their final state immediately when the viewer prefers reduced motion.
 */

import { animate, motion, useInView, useReducedMotion } from 'motion/react'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

const EASE = [0.16, 1, 0.3, 1] as const

/** Hands each Reveal on a page the next index, so items entering together stagger in order. */
const StaggerContext = createContext<{ next: () => number } | null>(null)

export function StaggerScope({ children }: { children: ReactNode }) {
  const counter = useRef(0)
  return <StaggerContext.Provider value={{ next: () => counter.current++ }}>{children}</StaggerContext.Provider>
}

export function Reveal({ children, className, as = 'div' }: {
  children: ReactNode; className?: string; as?: 'div' | 'section' | 'article'
}) {
  const reduce = useReducedMotion()
  const scope = useContext(StaggerContext)
  const [index] = useState(() => scope?.next() ?? 0)
  const Tag = motion[as]
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.55, delay: Math.min(index, 8) * 0.06, ease: EASE }}
    >
      {children}
    </Tag>
  )
}

/** A number that counts up from 0 the first time it scrolls into view, then follows updates. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true })
  const reduce = useReducedMotion()
  const shown = useRef(0)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (reduce || !inView) {
      if (reduce) { el.textContent = format(value); shown.current = value }
      return
    }
    const controls = animate(shown.current, value, {
      duration: 1.1, ease: EASE,
      onUpdate: (v) => { el.textContent = format(v); shown.current = v },
      // Always end on the exact value, never on the last interpolated frame.
      onComplete: () => { el.textContent = format(value); shown.current = value },
    })
    return () => controls.stop()
  }, [value, inView, reduce, format])

  // The final value is in the DOM text for screen readers and for no-JS / reduced motion.
  return <span ref={ref} aria-label={format(value)}>{format(reduce ? value : 0)}</span>
}
