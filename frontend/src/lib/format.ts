/** Formatting and the plain-language names of pipeline values. */

const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })
const nf2 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const nf3 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 })

export function num(v: unknown, digits: 0 | 1 | 2 | 3 = 0): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return [nf0, nf1, nf2, nf3][digits].format(n)
}

/** A 0–1 share shown as a percentage. */
export function pct(v: unknown, digits = 1): string {
  if (v === null || v === undefined || v === '') return '-'
  const n = Number(v)
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : String(v)
}

export function minutes(v: unknown): string {
  if (v === null || v === undefined) return '-'
  const n = Number(v)
  return Number.isFinite(n) ? `${n.toFixed(1)} min` : String(v)
}

const LABELS: Record<string, string> = {
  weekday: 'Weekday', weekend: 'Weekend', holiday: 'Holiday',
  early_morning: 'Early morning', morning_peak: 'Morning peak', midday: 'Midday',
  evening_peak: 'Evening peak', evening: 'Evening',
  brt: 'BRT', trunk: 'Trunk', local: 'Local', feeder: 'Feeder',
  add_trips: 'Add trips', larger_vehicle: 'Larger vehicle', smaller_vehicle: 'Smaller vehicle',
  reduce_frequency: 'Reduce frequency', no_change: 'No change',
  excess_demand: 'Excess demand', excess_supply: 'Excess supply', balanced: 'Balanced',
  insufficient_data: 'Insufficient data', too_little: 'Too little service', too_much: 'Too much service',
  well_matched: 'Well matched', underutilized: 'Underutilized', low_use_low_frequency: 'Low use, low frequency',
  adequate: 'Adequate', both_peaks: 'Both peaks', evening_congestion: 'Evening peak', morning_congestion: 'Morning peak',
  city_wide_event: 'City-wide event', local_event: 'Local event', normal: 'Normal',
  abnormal_delay: 'Abnormal delay', abnormal_travel_time: 'Abnormal travel time', demand_spike: 'Demand spike',
  demand_drop: 'Demand drop', duplicate_ticketing_signal: 'Duplicate ticketing', irregular_stop_activity: 'Irregular stop activity',
  unexpected_route_usage: 'Unexpected route usage', impossible_occupancy: 'Impossible occupancy',
  day_class: 'Day class', day_of_week: 'Day of week', direction: 'Direction', distance_band: 'Trip distance',
  hour: 'Hour of day', route: 'Route', route_type: 'Route type', time_period: 'Time of day', vehicle: 'Vehicle',
  persistent: 'Persistent', recurring: 'Recurring', one_off: 'One-off', none: 'None',
}

export function label(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-'
  const s = String(v)
  return LABELS[s] ?? s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export const DAY_CLASSES = ['weekday', 'weekend', 'holiday'] as const
export const TIME_PERIODS = ['early_morning', 'morning_peak', 'midday', 'evening_peak', 'evening'] as const
export const WEEKDAYS = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

/** Route classes -> status tone. Tone always ships with an icon and the class name. */
export const CLASS_TONE: Record<string, 'good' | 'warning' | 'serious' | 'critical' | 'neutral'> = {
  'High Performing': 'good',
  'Reliable but Underutilized': 'neutral',
  'Mixed / Needs Review': 'neutral',
  'High Demand but Unreliable': 'warning',
  'Low Performing': 'serious',
  'Overcrowded': 'critical',
  'Insufficient Data': 'neutral',
}

export const ROUTE_CLASSES = Object.keys(CLASS_TONE)
