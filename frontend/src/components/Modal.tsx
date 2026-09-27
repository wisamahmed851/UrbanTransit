/**
 * Modal dialog (CMD-027) on the native <dialog> element: showModal() gives the focus trap,
 * Escape to close and an inert page behind it; focus returns to the opening button on close.
 * It scales and fades in (transform/opacity; a short fade with reduced motion). Clicking the
 * backdrop closes it.
 */

import { X } from '@phosphor-icons/react'
import { useEffect, useRef, type ReactNode } from 'react'

export function Modal({ open, title, onClose, children }: {
 open: boolean; title: string; onClose: () => void; children: ReactNode
}) {
 const ref = useRef<HTMLDialogElement>(null)

 useEffect(() => {
  const dialog = ref.current
  if (!dialog) return
  if (open && !dialog.open) dialog.showModal()
  if (!open && dialog.open) dialog.close()
 }, [open])

 return (
  <dialog
   ref={ref}
   className="modal"
   aria-labelledby="modal-title"
   onClose={onClose}
   onCancel={(e) => { e.preventDefault(); onClose() }}
   onClick={(e) => { if (e.target === ref.current) onClose() }}
  >
   {open && (
    <>
     <header className="modal-head">
      <h2 id="modal-title">{title}</h2>
      <button type="button" className="modal-close" aria-label="Close" onClick={onClose}><X size={16} weight="bold" aria-hidden="true" /></button>
     </header>
     <div className="modal-body">{children}</div>
    </>
   )}
  </dialog>
 )
}
