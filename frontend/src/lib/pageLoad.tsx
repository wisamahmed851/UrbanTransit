/**
 * Page-load phases (CMD-027): loader first, then the page's entrance, never both at once.
 *
 *   loading   the route just opened; every request made now (useApi, useAllRows, the lazy
 *             page chunk) is tracked. The <PageLoader> shows; the page renders underneath,
 *             hidden, so its requests can start.
 *   ready     tracked requests have finished (at least MIN_MS after opening, at most MAX_MS so a
 *             slow API never traps the page). The loader starts its exit.
 *   revealed  the loader has finished leaving. Only now do the page entrance, the card reveals
 *             and the KPI counters run.
 *
 * Requests made after `ready` (a filter or tab change) are not tracked: those show skeletons
 * or a dimmed table in place, and the page itself stays put.
 *
 * Laravel analogy: none really; think of it as a per-page "pending jobs" counter.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Loading } from '../components/ui'
import { PageLoadContext, usePageLoad } from './pageLoadContext'

const MIN_MS = 350
const MAX_MS = 7000

const done = () => {}

/** Mount once per route (key it by pathname), around the page. */
export function PageLoadProvider({ children }: { children: ReactNode }) {
 const [ready, setReady] = useState(false)
 const [revealed, setRevealed] = useState(false)
 const pending = useRef(0)
 const readyRef = useRef(false)
 const opened = useRef(0)
 const timer = useRef<number | undefined>(undefined)

 const finish = useCallback(() => {
  if (readyRef.current) return
  const wait = Math.max(0, MIN_MS - (performance.now() - opened.current))
  window.clearTimeout(timer.current)
  timer.current = window.setTimeout(() => {
   if (pending.current === 0 && !readyRef.current) { readyRef.current = true; setReady(true) }
  }, wait)
 }, [])

 useEffect(() => {
  opened.current = performance.now()
  // Pages without any request: give their effects two frames to register, then finish.
  let raf = requestAnimationFrame(() => { raf = requestAnimationFrame(() => { if (pending.current === 0) finish() }) })
  const cap = window.setTimeout(() => { if (!readyRef.current) { readyRef.current = true; setReady(true) } }, MAX_MS)
  return () => { cancelAnimationFrame(raf); window.clearTimeout(cap); window.clearTimeout(timer.current) }
 }, [finish])

 const track = useCallback(() => {
  if (readyRef.current) return done
  pending.current += 1
  window.clearTimeout(timer.current)
  let settled = false
  return () => {
   if (settled) return
   settled = true
   pending.current -= 1
   if (pending.current === 0) finish()
  }
 }, [finish])

 const onLoaderGone = useCallback(() => setRevealed(true), [])
 const value = useMemo(() => ({ ready, revealed, track, onLoaderGone }), [ready, revealed, track, onLoaderGone])
 return <PageLoadContext.Provider value={value}>{children}</PageLoadContext.Provider>
}

/** Suspense fallback: keeps the loader up while a lazy page chunk downloads; if the loader has
 * already handed over (slow network), a skeleton holds the space until the page arrives. */
export function TrackSuspense() {
 const { track, ready } = usePageLoad()
 useEffect(() => track(), [track])
 return ready ? <Loading what="page" kind="block" /> : null
}
