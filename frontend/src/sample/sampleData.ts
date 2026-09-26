/**
 * SAMPLE DATA ONLY. Nothing here comes from the pipeline or from a model.
 *
 * Used where the backend explicitly answers "unavailable" (HTTP 503 stub): delay and
 * crowding predictions (no valid model yet) and Phase 7 recommendations (engine not built).
 * Values are generated deterministically from the inputs so the UI can be designed and
 * demonstrated; every screen that shows them wraps them in <Sample>. Delete this module
 * once the real endpoints return data.
 */

/** Deterministic 0..1 pseudo-random numbers from a string (same inputs, same sample). */
function seeded(seed: string): () => number {
  let h = 2166136261
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619)
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507)
    h = Math.imul(h ^ (h >>> 13), 3266489909)
    return ((h ^= h >>> 16) >>> 0) / 4294967296
  }
}

export interface PredictionInput { route_id: string; service_date: string; hour: number; direction: number }

export const SEVERITIES = ['On Time', 'Minor', 'Moderate', 'Severe'] as const

export function sampleDelayPrediction(input: PredictionInput) {
  const rnd = seeded(`delay|${input.route_id}|${input.service_date}|${input.hour}|${input.direction}`)
  const peak = [7, 8, 9, 16, 17, 18].includes(input.hour) ? 1.6 : 1
  const raw = [3 + rnd() * 3, (0.6 + rnd()) * peak, (0.3 + rnd() * 0.6) * peak, rnd() * 0.2 * peak]
  const total = raw.reduce((a, b) => a + b, 0)
  const probabilities = SEVERITIES.map((s, i) => ({ severity: s, probability: raw[i] / total }))
  const top = probabilities.reduce((a, b) => (b.probability > a.probability ? b : a))
  return { predicted: top.severity, probabilities }
}

export function sampleCrowdingPrediction(input: PredictionInput) {
  const rnd = seeded(`crowd|${input.route_id}|${input.service_date}|${input.hour}|${input.direction}`)
  const peak = [7, 8, 9, 16, 17, 18].includes(input.hour) ? 0.35 : 0
  const load = Math.min(1.3, 0.25 + rnd() * 0.5 + peak)
  const probability = Math.min(0.97, Math.max(0.02, (load - 0.55) * 1.6))
  return { expected_load: load, crowding_probability: probability, crowded: probability >= 0.5 }
}

export interface SampleRecommendation {
  id: string
  route_id: string
  action: string
  when: string
  why: string
  expected_effect: string
  priority: 'High' | 'Medium' | 'Low'
}

/** Illustrative recommendation cards: the layout Phase 7 output is expected to fill. */
export const SAMPLE_RECOMMENDATIONS: SampleRecommendation[] = [
  { id: 's1', route_id: 'R0xx', action: 'Add two trips per hour', when: 'Weekday morning peak, outbound',
    why: 'Buses leave the busiest stop above capacity on most weekdays.', expected_effect: 'Peak load from about 110% to about 85%', priority: 'High' },
  { id: 's2', route_id: 'R0xx', action: 'Swap standard buses for articulated', when: 'Weekday evening peak, both directions',
    why: 'Frequency is already high; the extra space is needed per bus, not per hour.', expected_effect: 'Riders left behind cut by about two thirds', priority: 'High' },
  { id: 's3', route_id: 'R0xx', action: 'Retime departures to even gaps', when: 'Midday, inbound',
    why: 'Buses often run in pairs, then leave a long gap.', expected_effect: 'Fewer bunched departures', priority: 'Medium' },
  { id: 's4', route_id: 'R0xx', action: 'Reduce to three trips per hour', when: 'Weekend early morning',
    why: 'Average load stays under 20% while running every 12 minutes.', expected_effect: 'Frees one bus for peak service', priority: 'Low' },
]
