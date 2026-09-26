/** Response shapes of the Flask API (documentation/backend_api.md). */

import type { Row } from './client'

export interface User {
  id: number
  username: string
  email: string | null
  is_active: boolean
  roles: string[]
  permissions: string[]
  created_at: string | null
  last_login_at: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: 'Bearer'
  expires_in: number
  user: User
}

export interface TableInfo {
  name: string
  rows: number
  columns: { name: string; type: string }[]
  filters: string[]
}

export interface RowsResponse<R = Row> {
  table: string
  total: number
  limit: number
  offset: number
  filters: string[]
  rows: R[]
}

export interface MetricRow {
  id: number
  source_file: string
  task: string
  algorithm: string
  split_type: string
  metric_name: string
  metric_value: number | null
  extra_json: Record<string, unknown> | null
  validity_flag: string | null
  validity_note: string | null
}

export interface MetricsResponse {
  total: number
  warnings: { task: string; validity_flag: string; message: string }[]
  rows: MetricRow[]
  source: string
}

export interface ClusterProfile {
  prediction: number
  route_load_factor: number
  route_reliability_delay_min: number
  trip_punctuality_rate: number
  avg_trip_boardings: number
  avg_daily_boardings: number
  crowding_rate: number
  bunching_rate: number
  arrival_delay_std_min: number
  routes: number
  plain_language_label: string
}

export interface ClustersResponse {
  algorithm: string
  k: number
  clusters: ClusterProfile[]
  notes: string[]
  source: string
}

export interface AuditEntry {
  id: number
  actor: string
  action: string
  entity: string | null
  timestamp: string
  details: Record<string, unknown> | null
}

// ---- Model serving (CMD-024) ----------------------------------------------------------

export interface MetricRowWithPipeline extends MetricRow { pipeline: 'spark' | 'python' }

export interface ModelCard {
  task: string
  algorithm: string
  version: string
  file?: string
  pipeline: string
  trained_on?: string
  test_accuracy: number
  test_macro_f1: number
  metrics_source: string
  meets_srs_target: boolean
  srs_target: string
}

export interface TripRef { route_id: string; direction: number; service_date: string; hour: number; day_type: string }

export interface Observed {
  window: string
  trips: number
  crowded_trip_share: number | null
  mean_occupancy: number | null
  p90_occupancy: number | null
  mean_boardings: number | null
  mean_delay_min: number | null
}

interface PredictionBase {
  estimate: true
  trip: TripRef
  inputs: Record<string, string | number | null>
  observed: Observed
  model: ModelCard
  warnings: string[]
}

export interface CrowdingPrediction extends PredictionBase {
  task: 'crowding_flag'
  prediction: { crowded: boolean; probability: number; threshold: number; meaning: string }
}

export interface DelayPrediction extends PredictionBase {
  task: 'delay_severity'
  prediction: { severity: string; probabilities: { severity: string; probability: number }[]; bands: string }
}

export type RiskRow = {
  route_id: string
  direction: number
  hour: number
  vehicle_id: string
  probability: number
  flagged: boolean
  observed_crowded_share: number | null
  observed_mean_occupancy: number | null
  trips_observed: number
}

export interface CrowdingRiskResponse {
  service_date: string
  day_type: string
  threshold: number
  cells: number
  flagged: number
  limit: number
  rows: RiskRow[]
  model: ModelCard
}

export interface DemandModelCard {
  task: string
  algorithm: string
  version: string
  pipeline: string
  features: string[]
  test: { mae: number; rmse: number; mape: number; r2: number; rows: number } | null
  srs_target: { rule: string; baseline_test_mae: number; selected_test_mae: number; improvement_pct: number; met: boolean } | null
}

export interface ForecastErrors { mae?: number; rmse?: number; mape?: number | null }

export interface RouteForecast {
  route_id: string
  horizon_days: number
  last_observed_date: string
  history: { date: string; actual: number }[]
  backtest: { date: string; actual: number; predicted: number; baseline: number }[]
  backtest_errors: { model: ForecastErrors; baseline_28day: ForecastErrors }
  forecast: { date: string; predicted: number }[]
  model: DemandModelCard
  notes: string[]
}

export interface NetworkForecast {
  horizon_days: number
  routes: number
  last_observed_date: string
  history: { date: string; actual: number }[]
  forecast: { date: string; predicted: number }[]
  by_route: { route_id: string; recent_28day_mean: number; forecast_mean: number; change_pct: number | null; peak_day: string; peak_value: number }[]
  model: DemandModelCard
}

export interface WhatIfState {
  hour: number
  headway_min: number
  trips_per_hour: number
  capacity_per_trip: number
  capacity_per_hour: number
  peak_load_per_trip: number
  demand_per_hour: number
  occupancy: number
  occupancy_category: string
  waiting_time_min: number
  demand_coverage: number
  crowding_probability: number | null
  delay_risk: number | null
}

export interface WhatIfResponse {
  estimate: true
  label: string
  scenario: { type: string; description: string; route_id: string; direction: number; service_date: string; day_type: string; hour: number; params: Record<string, number> }
  baseline: WhatIfState
  result: WhatIfState
  changes: { measure: keyof WhatIfState; before: number | string; after: number | string; change: number | null }[]
  notes: string[]
  assumptions: string[]
  observed_window: string
}

export type Recommendation = {
  recommendation_id: string
  subject_id: string
  category: string
  priority: 'Critical' | 'High' | 'Medium' | 'Low'
  priority_rank: number
  action: string
  evidence: string
  estimated_impact: string | null
}

export interface RecommendationsResponse {
  total: number
  limit: number
  offset: number
  rows: Recommendation[]
  summary: { total: number; by_priority: Record<string, number>; by_category: Record<string, number> }
  source: string
}

export interface ComparisonTask {
  task: 'delay_severity' | 'crowding_flag' | 'daily_boardings'
  title: string
  caveat: string
  cases: number
  agreement_rate: number | null
  spark_correct_rate: number | null
  python_correct_rate: number | null
  by_status: Record<string, number>
}

export interface ComparisonResponse { tasks: ComparisonTask[]; cases: number; overall_agreement_rate: number | null; source: string }

export type ComparisonCase = {
  task: string
  case_id: string
  actual: string
  spark_prediction: string
  python_prediction: string
  spark_value: string | null
  python_value: string | null
  absolute_difference: number | null
  match: boolean
  agreement_status: string
  explanation: string | null
}

export interface ModelVersionRow {
  task: string
  algorithm: string
  version: string
  is_active: boolean
  registered_at: string
  metrics: Record<string, unknown> & { srs_target?: Record<string, unknown>; test?: Record<string, number>; verified_on_this_machine?: string }
}

export interface PythonCluster {
  cluster: number
  profile_label: string
  routes: number
  route_ids: string[]
  avg_occupancy: number
  avg_delay_minutes: number
  reliability_score: number
  trip_frequency: number
  peak_demand_ratio: number
  avg_daily_boardings: number
  demand_mom_growth: number
}
