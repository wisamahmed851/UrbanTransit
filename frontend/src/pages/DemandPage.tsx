import { useState } from 'react'
import { DataTable, Pager } from '../components/DataTable'
import { FilterBar, type Filters } from '../components/FilterBar'
import { ErrorNotice, Loading, PageHead, Panel } from '../components/ui'
import { label, num } from '../lib/format'
import { useRows } from '../lib/useApi'

const OD_FILTERS = ['route_id', 'stop_id', 'direction', 'day_class', 'time_period']

export function DemandPage() {
  const [filters, setFilters] = useState<Filters>({ day_class: 'weekday', time_period: 'morning_peak' })
  const [offset, setOffset] = useState(0)
  const [sort, setSort] = useState('-est_passengers')
  const od = useRows('od_matrix', { ...filters, sort, limit: 25, offset })
  const pairs = useRows('flow_od_pairs', { limit: 15, sort: '-est_journeys_per_day' })
  const events = useRows('special_event_dates', { limit: 400, sort: 'service_date' })
  const anomalies = useRows('anomaly_summary', { limit: 20, sort: '-signals' })

  const eventDays = (events.data?.rows ?? []).filter((r) => r.date_status !== 'normal')

  return (
    <div className="page">
      <PageHead title="Demand and journeys">
        Where people travel from and to. Journeys come from registered smart cards (about 3 to 4% of riders), scaled up to
        estimate everyone. Cells built from only a few card journeys are rough; the raw card count is shown next to the estimate.
      </PageHead>

      <Panel title="Origin and destination" note="Estimated passengers between two stops over the year, for the chosen route, day and time.">
        <FilterBar supported={OD_FILTERS} value={filters} onChange={(f) => { setFilters(f); setOffset(0) }} />
        <div style={{ marginTop: '0.9rem' }}>
          {od.error ? <ErrorNotice error={od.error} /> : od.loading && !od.data ? <Loading what="journeys" /> : (
            <>
              <DataTable rows={od.data?.rows ?? []} stale={od.loading} sort={sort} onSort={(s) => { setSort(s); setOffset(0) }} columns={[
                { key: 'origin_stop_name', label: 'From', render: (r) => `${r.origin_stop_name} (${r.origin_stop_id})` },
                { key: 'destination_stop_name', label: 'To', render: (r) => `${r.destination_stop_name} (${r.destination_stop_id})` },
                { key: 'route_id', label: 'Route' },
                { key: 'direction', label: 'Dir.' },
                { key: 'day_class', label: 'Day', render: (r) => label(r.day_class) },
                { key: 'time_period', label: 'Time', render: (r) => label(r.time_period) },
                { key: 'est_passengers', label: 'Est. passengers', num: true, render: (r) => num(r.est_passengers) },
                { key: 'card_journeys', label: 'Card journeys', num: true },
                { key: 'days_observed', label: 'Days seen', num: true },
              ]} />
              {od.data && <Pager total={od.data.total} limit={od.data.limit} offset={offset} onChange={setOffset} />}
            </>
          )}
        </div>
      </Panel>

      <div className="grid-2">
        <Panel title="Busiest stop pairs" note="All routes combined, estimated journeys per day.">
          <DataTable rows={pairs.data?.rows ?? []} columns={[
            { key: 'origin_stop_id', label: 'From' },
            { key: 'destination_stop_id', label: 'To' },
            { key: 'est_journeys_per_day', label: 'Journeys / day', num: true, render: (r) => num(r.est_journeys_per_day) },
            { key: 'avg_journey_km', label: 'Average km', num: true, render: (r) => num(r.avg_journey_km, 1) },
            { key: 'routes_used', label: 'Routes', num: true },
          ]} />
        </Panel>

        <Panel title="Unusual activity" note="Signals worth a look: each type counts days or entities that broke from their usual pattern.">
          {anomalies.error ? <ErrorNotice error={anomalies.error} /> : (
            <DataTable rows={anomalies.data?.rows ?? []} columns={[
              { key: 'anomaly_type', label: 'Signal', render: (r) => label(r.anomaly_type) },
              { key: 'entity_type', label: 'Applies to', render: (r) => label(r.entity_type) },
              { key: 'signals', label: 'Signals', num: true, render: (r) => num(r.signals) },
              { key: 'entities', label: 'Distinct', num: true, render: (r) => num(r.entities) },
              { key: 'dates', label: 'Days', num: true, render: (r) => num(r.dates) },
            ]} />
          )}
        </Panel>
      </div>

      <Panel title="Special event days" note="Days when demand on a route was 1.5× or more (spike) or half or less (drop) of the same weekday's median over the previous 8 weeks.">
        <DataTable rows={eventDays} columns={[
          { key: 'service_date', label: 'Date' },
          { key: 'date_status', label: 'Type', render: (r) => label(r.date_status) },
          { key: 'holiday_name', label: 'Holiday' },
          { key: 'routes_spiking', label: 'Routes up', num: true },
          { key: 'routes_dropping', label: 'Routes down', num: true },
          { key: 'max_demand_ratio', label: 'Largest jump', num: true, render: (r) => `${num(r.max_demand_ratio, 2)}×` },
          { key: 'spiking_routes', label: 'Routes spiking', wrap: true },
        ]} />
      </Panel>
    </div>
  )
}
