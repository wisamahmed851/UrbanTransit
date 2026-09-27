/**
 * Cursor follower (CMD-026): a gold dot on the pointer and a blue ring that trails it, filling
 * softly over anything clickable and pressing in on mouse-down. Feedback, not decoration: it
 * shows what will respond to a click.
 *
 * - The system cursor stays visible; the ring has pointer-events: none, so nothing is blocked.
 * - Only on fine pointers (mouse, trackpad) and never with prefers-reduced-motion; it removes
 *   itself if either changes.
 * - Moves with transform only, in one requestAnimationFrame loop that stops as soon as the
 *   ring catches up, so an idle page costs nothing (60fps-animation skill).
 */

import { useEffect, useRef } from 'react'

const CLICKABLE = 'a, button, select, input, textarea, summary, label, [role="button"], [role="tab"], .dt-paging-button, th.dt-orderable-asc, th.dt-orderable-desc'
const FOLLOW = 0.2   // share of the remaining distance the ring covers per frame

export function CursorFollower() {
 const ring = useRef<HTMLDivElement>(null)
 const dot = useRef<HTMLDivElement>(null)

 useEffect(() => {
  const fine = window.matchMedia('(pointer: fine)')
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')
  const root = document.documentElement
  let target = { x: -100, y: -100 }, pos = { x: -100, y: -100 }, frame = 0, active = false

  const place = () => {
   pos.x += (target.x - pos.x) * FOLLOW
   pos.y += (target.y - pos.y) * FOLLOW
   if (ring.current) ring.current.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0)`
   frame = Math.abs(target.x - pos.x) + Math.abs(target.y - pos.y) > 0.3 ? requestAnimationFrame(place) : 0
  }
  const move = (e: PointerEvent) => {
   if (e.pointerType !== 'mouse') return
   target = { x: e.clientX, y: e.clientY }
   if (dot.current) dot.current.style.transform = `translate3d(${target.x}px, ${target.y}px, 0)`
   if (!root.classList.contains('cursor-on')) { pos = { ...target }; root.classList.add('cursor-on') }
   if (!frame) frame = requestAnimationFrame(place)
  }
  const over = (e: PointerEvent) => root.classList.toggle('cursor-hot', !!(e.target as Element | null)?.closest?.(CLICKABLE))
  const leave = () => root.classList.remove('cursor-on')
  const down = () => root.classList.add('cursor-down')
  const up = () => root.classList.remove('cursor-down')

  const start = () => {
   if (active) return
   active = true
   window.addEventListener('pointermove', move, { passive: true })
   window.addEventListener('pointerover', over, { passive: true })
   window.addEventListener('pointerdown', down, { passive: true })
   window.addEventListener('pointerup', up, { passive: true })
   document.addEventListener('pointerleave', leave)
  }
  const stop = () => {
   active = false
   window.removeEventListener('pointermove', move)
   window.removeEventListener('pointerover', over)
   window.removeEventListener('pointerdown', down)
   window.removeEventListener('pointerup', up)
   document.removeEventListener('pointerleave', leave)
   cancelAnimationFrame(frame); frame = 0
   root.classList.remove('cursor-on', 'cursor-hot', 'cursor-down')
  }
  const sync = () => (fine.matches && !reduce.matches ? start() : stop())
  sync()
  fine.addEventListener('change', sync)
  reduce.addEventListener('change', sync)
  return () => { stop(); fine.removeEventListener('change', sync); reduce.removeEventListener('change', sync) }
 }, [])

 return (
  <>
   <div ref={ring} className="cursor-ring" aria-hidden="true"><i /></div>
   <div ref={dot} className="cursor-dot" aria-hidden="true" />
  </>
 )
}
