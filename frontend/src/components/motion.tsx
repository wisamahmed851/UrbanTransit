/**
 * Motion building blocks (Motion, formerly Framer Motion). Every animation here has a job:
 *
 * - <Reveal>: cards and charts scale up, rise and fade in once, in reading order, with a
 *  visible stagger (hierarchy). They wait for the page loader to leave (lib/pageLoad.tsx), so
 *  the loader and the entrance never run together.
 * - <CountUp> / <CountUpText>: KPI values count up from 0 in whole numbers and land on the
 *  exact value (draws the eye to the KPIs).
 * - <Swap>: content behind a tab or segment slides and fades when the choice changes.
 *
 * Only transform and opacity are animated (60fps-animation skill). Reduced motion is tiered
 * (accessible-animation skill): no movement or scaling, a short fade, counters show the value.
 */

import { AnimatePresence, animate, motion, useInView, useReducedMotion } from 'motion/react'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { usePageLoad } from '../lib/pageLoadContext'

const EASE = [0.16, 1, 0.3, 1] as const
const STAGGER = 0.09        // seconds between consecutive items
const STAGGER_CAP = 10      // later items share the last delay, so nothing waits over ~1 s

/** Hands each Reveal on a page the next index, so items entering together stagger in order. */
const StaggerContext = createContext<{ next: () => number } | null>(null)

export function StaggerScope({ children }: { children: ReactNode }) {
 // Items mounting together share one sequence; a later batch (new rows after a filter change)
 // starts its own sequence at 0 instead of queueing behind everything shown so far.
 const counter = useRef(0)
 const last = useRef(0)
 const next = () => {
  const now = performance.now()
  if (now - last.current > 300) counter.current = 0
  last.current = now
  return counter.current++
 }
 return <StaggerContext.Provider value={{ next }}>{children}</StaggerContext.Provider>
}

export function Reveal({ children, className, as = 'div' }: {
 children: ReactNode; className?: string; as?: 'div' | 'section' | 'article'
}) {
 const reduce = useReducedMotion()
 const scope = useContext(StaggerContext)
 const { revealed } = usePageLoad()
 const [index] = useState(() => scope?.next() ?? 0)
 const ref = useRef<HTMLElement>(null)
 const inView = useInView(ref, { once: true, amount: 0.12 })
 const Tag = motion[as]
 const hidden = reduce ? { opacity: 0 } : { opacity: 0, y: 24, scale: 0.94 }
 const shown = { opacity: 1, y: 0, scale: 1 }
 return (
  <Tag
   ref={ref as never}
   className={className}
   initial={hidden}
   animate={revealed && inView ? shown : hidden}
   transition={reduce ? { duration: 0.15 } : { duration: 0.6, delay: Math.min(index, STAGGER_CAP) * STAGGER, ease: EASE }}
  >
   {children}
  </Tag>
 )
}

/** Starts once the loader has gone and the element is on screen; returns [ref, go, reduce]. */
function useCountStart() {
 const ref = useRef<HTMLSpanElement>(null)
 const inView = useInView(ref, { once: true })
 const { revealed } = usePageLoad()
 const reduce = useReducedMotion()
 return [ref, revealed && inView, reduce] as const
}

/** A number that counts up from 0 in whole steps, then follows updates, ending on the exact value. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
 const [ref, go, reduce] = useCountStart()
 const shown = useRef(0)

 useEffect(() => {
  const el = ref.current
  if (!el) return
  if (reduce) { el.textContent = format(value); shown.current = value; return }
  if (!go) return
  const controls = animate(shown.current, value, {
   duration: 1.2, ease: EASE,
   onUpdate: (v) => { el.textContent = format(Math.round(v)); shown.current = v },
   // Always end on the exact value, never on the last interpolated frame.
   onComplete: () => { el.textContent = format(value); shown.current = value },
  })
  return () => controls.stop()
 }, [value, go, reduce, format, ref])

 // The final value is in the accessible name for screen readers.
 return <span ref={ref} aria-label={format(value)}>{format(reduce ? value : 0)}</span>
}

// "232,186", "-2.4%", "193", "$1.5k": sign, digits with grouping, optional decimals, then a suffix.
const NUMBER_IN_TEXT = /^([^\d-]*)(-?)([\d,]+)(\.\d+)?(.*)$/

/**
 * Counts up a value that is already formatted text. It counts the whole part in whole steps
 * with the same grouping and suffix, then shows the original text exactly (decimals included).
 * Text that is not a number is shown as is.
 */
export function CountUpText({ text }: { text: string }) {
 const [ref, go, reduce] = useCountStart()
 const match = NUMBER_IN_TEXT.exec(text.trim())
 const target = match ? Number(match[3].replace(/,/g, '')) : NaN
 const grouped = !!match && match[3].includes(',')
 const piece = (n: number) => `${match![1]}${match![2]}${grouped ? Math.round(n).toLocaleString('en-US') : Math.round(n)}${match![5]}`

 useEffect(() => {
  const el = ref.current
  if (!el) return
  if (!match || !Number.isFinite(target) || reduce) { el.textContent = text; return }
  if (!go) { el.textContent = piece(0); return }
  const controls = animate(0, target, {
   duration: 1.2, ease: EASE,
   onUpdate: (v) => { el.textContent = piece(v) },
   onComplete: () => { el.textContent = text },
  })
  return () => controls.stop()
 // eslint-disable-next-line react-hooks/exhaustive-deps
 }, [text, go, reduce])

 // Always the same element, so the in-view observer is attached even while the value is
 // still a placeholder ("…") that becomes a number later.
 const numeric = !!match && Number.isFinite(target)
 return <span ref={ref} aria-label={text}>{!numeric || reduce ? text : piece(0)}</span>
}

/** Content behind a tab, segment or filter: slides and fades out, the new content in. */
export function Swap({ k, children }: { k: string; children: ReactNode }) {
 const reduce = useReducedMotion()
 return (
  <AnimatePresence mode="wait" initial={false}>
   <motion.div
    key={k}
    initial={reduce ? { opacity: 0 } : { opacity: 0, x: 14 }}
    animate={{ opacity: 1, x: 0 }}
    exit={reduce ? { opacity: 0 } : { opacity: 0, x: -14 }}
    transition={{ duration: reduce ? 0.12 : 0.22, ease: EASE }}
   >
    {children}
   </motion.div>
  </AnimatePresence>
 )
}
