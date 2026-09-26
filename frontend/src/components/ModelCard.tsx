/** Which saved model produced an answer, how it scored on unseen data, and whether that meets the SRS. */

import type { ModelCard as Card } from '../api/types'
import { pct } from '../lib/format'
import { Status } from './ui'

export function ModelCard({ model }: { model: Card }) {
  return (
    <dl className="model-card">
      <div><dt>Model</dt><dd>{model.algorithm} {model.version} · {model.pipeline}</dd></div>
      <div><dt>Test accuracy</dt><dd>{pct(model.test_accuracy, 1)}</dd></div>
      <div><dt>Test macro F1</dt><dd>{model.test_macro_f1.toFixed(3)}</dd></div>
      <div><dt>SRS target</dt><dd>{model.meets_srs_target
        ? <Status tone="good">Met</Status>
        : <Status tone="serious">Not met</Status>} <span className="muted">{model.srs_target}</span></dd></div>
    </dl>
  )
}

/** Warnings travel with the answer they qualify. */
export function Warnings({ items }: { items: string[] }) {
  if (!items.length) return null
  return (
    <div className="notice notice-warn" role="note">
      {items.map((w) => <span key={w}>{w}</span>)}
    </div>
  )
}

/** Every model-derived figure is an estimate; this tag says so next to it. */
export function EstimateTag({ children = 'Model estimate' }: { children?: string }) {
  return <span className="estimate-tag">{children}</span>
}
