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
