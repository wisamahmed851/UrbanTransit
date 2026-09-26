/** Shared trip-request helpers for the Predictions and What-if pages (kept apart from the components for fast refresh). */

import { useApi } from './useApi'

export interface TripInput { route_id: string; direction: number; service_date: string; hour: number }

/** Tomorrow as YYYY-MM-DD in the viewer's time zone. */
export function tomorrow(): string {
  const d = new Date(Date.now() + 86_400_000)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const DEFAULT_TRIP: TripInput = { route_id: 'R012', direction: 0, service_date: tomorrow(), hour: 8 }

export interface RouteOption { route_id: string; route_code: string; route_name: string }

export function useRouteOptions() {
  return useApi<{ rows: RouteOption[] }>('/admin/routes', { limit: 1000 })
}
