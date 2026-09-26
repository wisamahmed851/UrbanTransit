import { ArrowsInLineHorizontal, ArrowsOutLineHorizontal, Clock, UsersThree } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { DataTable } from '../components/DataTable'
import { FilterBar, type Filters } from '../components/FilterBar'
import { ErrorNotice, Loading, PageHead, Panel, Stats } from '../components/ui'
import { label, num, pct } from '../lib/format'
import { useAllRows, useRows } from '../lib/useApi'

const whole = (n: number) => num(Math.round(n))
const SUPPORTED = ['route_id', 'direction', 'day_class', 'time_period']

export function CrowdingPage() {
  const [filters, setFilters] = useState<Filters>({})
  const gap = useAllRows('demand_supply_gap', filters)
  const freq = useAllRows('service_frequency', filters)
  const under = useAllRows('underutilized_services', filters)
  const persistent = useRows('persistent_overcrowding', {
    route_id: filters.route_id, direction: filters.direction, time_period: filters.time_period, limit: 25, sort: '-overload_day_share',
  })

  const count = <T extends Record<string, unknown>>(rows: T[] | null, key: string, value: string) =>
    rows ? rows.filter((r) => r[key] === value).length : '…'
  const suggestions = (gap.rows ?? []).filter((r) => r.suggestion && r.suggestion !== 'no_change')
    .sort((a, b) => Number(b.utilization) - Number(a.utilization))
  const underused = (under.rows ?? []).filter((r) => r.utilization_status === 'underutilized')
    .sort((a, b) => Number(a.avg_occupancy) - Number(b.avg_occupancy))
  const error = gap.error ?? freq.error ?? under.error

  return (
    <div className="page">
      <PageHead title="Crowding and capacity">
        Each service period is a route, direction, type of day and time of day. Load is measured at the busiest point of
        each counted trip. Trips without a passenger counter are left out, not counted as empty.
      </PageHead>
      <FilterBar supported={SUPPORTED} value={filters} onChange={setFilters} />
      {error && <ErrorNotice error={error} />}

      <Stats items={[
        { label: 'Periods with more riders than space', icon: UsersThree, format: whole, value: count(gap.rows, 'gap_status', 'excess_demand'), sub: '90%+ of capacity used, or riders left behind' },
        { label: 'Periods with far more space than riders', icon: ArrowsOutLineHorizontal, format: whole, value: count(gap.rows, 'gap_status', 'excess_supply'), sub: 'under 30% of capacity used' },
        { label: 'Too little service', icon: Clock, format: whole, value: count(freq.rows, 'frequency_match', 'too_little'), sub: 'average load 85%+ or often overloaded' },
        { label: 'Underused service', icon: ArrowsInLineHorizontal, format: whole, value: under.rows ? underused.length : '…', sub: 'low load at 2+ trips an hour' },
      ]} />

      <Panel title="Capacity changes suggested by the analysis" note="From the Phase 5 demand and supply analysis: the vehicle size or frequency that would bring load to 85%. These are analysis results, not approved plans.">
        {gap.loading ? <Loading /> : (
          <DataTable rows={suggestions.slice(0, 40)} empty="No capacity changes suggested for these filters." columns={[
            { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}>{String(r.route_id)}</Link> },
            { key: 'direction', label: 'Dir.' },
            { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
            { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
            { key: 'utilization', label: 'Capacity used', num: true, render: (r) => pct(r.utilization, 0) },
            { key: 'denied_per_trip', label: 'Left behind per trip', num: true, render: (r) => num(r.denied_per_trip, 1) },
            { key: 'suggestion', label: 'Suggestion', render: (r) => label(r.suggestion) },
            { key: 'suggested_vehicle_type', label: 'Vehicle', render: (r) => label(r.suggested_vehicle_type) },
            { key: 'extra_trips_per_hour', label: 'Extra trips / hour', num: true, render: (r) => num(r.extra_trips_per_hour, 1) },
          ]} />
        )}
        {suggestions.length > 40 && <p className="panel-note">Showing the 40 busiest of {suggestions.length.toLocaleString()}. Use the Data explorer to export all of them.</p>}
      </Panel>

      <div style={{ display: 'grid', gap: 'var(--gap)' }}>
        <Panel title="Where overcrowding keeps coming back" note="Route, direction, weekday and time of day, ranked by the share of normal days with an overloaded trip.">
          {persistent.error ? <ErrorNotice error={persistent.error} /> : (
            <DataTable rows={persistent.data?.rows ?? []} columns={[
              { key: 'route_id', label: 'Route' },
              { key: 'direction', label: 'Dir.' },
              { key: 'day_of_week', label: 'Weekday', render: (r) => ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][Number(r.day_of_week)] },
              { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
              { key: 'overload_day_share', label: 'Days overloaded', num: true, render: (r) => `${pct(r.overload_day_share, 0)} (${r.days_overloaded}/${r.days_observed})` },
              { key: 'overload_pattern', label: 'Pattern', render: (r) => label(r.overload_pattern) },
            ]} />
          )}
        </Panel>

        <Panel title="Underused service" note="Emptiest first. Only periods running at least 2 trips an hour, so cutting would not remove coverage.">
          {under.loading ? <Loading /> : (
            <DataTable rows={underused.slice(0, 25)} empty="No underused service for these filters." columns={[
              { key: 'route_id', label: 'Route' },
              { key: 'direction', label: 'Dir.' },
              { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
              { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
              { key: 'trips_per_hour', label: 'Trips / hour', num: true, render: (r) => num(r.trips_per_hour, 1) },
              { key: 'avg_occupancy', label: 'Average load', num: true, render: (r) => pct(r.avg_occupancy, 0) },
            ]} />
          )}
        </Panel>
      </div>
    </div>
  )
}
