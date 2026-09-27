import { CalendarBlank, ChartLineUp, Target, TrendUp } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { NetworkForecast, RouteForecast, StopPeriodForecast, StopPeriodOptions } from '../api/types'
import { ChartFrame, LinesChart } from '../components/charts'
import { DataTable } from '../components/DataTable'
import { EstimateTag } from '../components/ModelCard'
import { RouteSelect } from '../components/TripForm'
import { ErrorNotice, Loading, PageHead, Panel, Segmented, Stats, Status } from '../components/ui'
import { num } from '../lib/format'
import { useApi } from '../lib/useApi'

const HORIZONS = ['7', '14', '28', '56'] as const
type Horizon = (typeof HORIZONS)[number]
const whole = (v: number) => num(Math.round(v))
const shortDate = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

export function ForecastPage() {
 const [horizon, setHorizon] = useState<Horizon>('14')
 const [route, setRoute] = useState('R001')
 const network = useApi<NetworkForecast>('/forecasts/demand/network', { horizon })
 const single = useApi<RouteForecast>('/forecasts/demand', { route_id: route, horizon, history: 60 })
 const [stop, setStop] = useState('')
 const [stopPeriod, setStopPeriod] = useState('am_peak')
 const stopOptions = useApi<StopPeriodOptions>('/forecasts/demand/stop-period/options')
 const activeStop = stop || stopOptions.data?.stops[0]?.stop_id || ''
 const availablePeriods = stopOptions.data?.stops.find((s) => s.stop_id === activeStop)?.periods ?? []
 const activePeriod = availablePeriods.includes(stopPeriod) ? stopPeriod : (availablePeriods[0] ?? '')
 const stopForecast = useApi<StopPeriodForecast>(activeStop && activePeriod ? '/forecasts/demand/stop-period' : null,
  { stop_id: activeStop, period: activePeriod, horizon, history: 60 })
 const n = network.data

 const next = n?.forecast[0]
 const recent7 = n ? n.history.slice(-7).reduce((s, h) => s + h.actual, 0) / 7 : 0
 const ahead7 = n ? n.forecast.slice(0, 7).reduce((s, f) => s + f.predicted, 0) / Math.min(7, n.forecast.length) : 0
 const target = n?.model.srs_target

 return (
  <div className="page">
   <PageHead title="Demand forecast">
    Daily boardings per route, forecast by the saved random forest from each route's earlier days. The
    forecast starts the day after the last day of data and is an estimate; its errors grow with the horizon.
   </PageHead>

   <div className="filters">
    <Segmented label="Forecast horizon" value={horizon} onChange={setHorizon}
     options={HORIZONS.map((h) => ({ value: h, label: `${h} days` }))} />
    <EstimateTag>Forecast values are estimates</EstimateTag>
   </div>

   {network.error && <ErrorNotice error={network.error} />}
   <Stats items={[
    { label: 'Next day, all routes', icon: CalendarBlank, value: next ? next.predicted : '…', format: whole, sub: next ? shortDate(next.date) : undefined },
    { label: 'Next 7 days vs last 7', icon: TrendUp, value: n ? `${ahead7 >= recent7 ? '+' : ''}${((ahead7 - recent7) / recent7 * 100).toFixed(1)}%` : '…', sub: 'average daily boardings' },
    { label: 'Test error (MAE)', icon: Target, value: target ? target.selected_test_mae : '…', format: whole, sub: target ? `boardings per route-day; baseline ${whole(target.baseline_test_mae)}` : undefined },
    { label: 'Better than baseline', icon: ChartLineUp, value: target ? `${target.improvement_pct}%` : '…', sub: target?.met ? 'SRS step 24 met: beats the 28-day average' : undefined },
   ]} />

   <Panel title="Network total" note={n ? `Sum of ${n.routes} routes. Last observed day ${n.last_observed_date}.` : undefined}>
    {!n ? <Loading what="forecast" /> : <NetworkChart n={n} />}
   </Panel>

   <Panel title={`Route ${route}`} note="Observed days, the model's one-day-ahead predictions on the test period (July and August 2026, not used in training), the 28-day-average baseline, and the forecast."
    action={<label className="field">Route<RouteSelect value={route} onChange={setRoute} /></label>}>
    {single.error ? <ErrorNotice error={single.error} /> : !single.data ? <Loading what="route forecast" /> : <RouteChart f={single.data} stale={single.loading} />}
   </Panel>

   <Panel title={`Stop-period tap-ins${activeStop ? `: ${activeStop} / ${activePeriod.replace('_', ' ')}` : ''}`}
    note="Ticket entry tap-ins at one stop and service period. This is not an estimate of cash riders or all passenger boardings."
    action={<div className="filters">
     <label className="field">Stop
      <select value={activeStop} onChange={(e) => { setStop(e.target.value); setStopPeriod('am_peak') }}>
       {stopOptions.data?.stops.map((s) => <option key={s.stop_id} value={s.stop_id}>{s.stop_id}</option>)}
      </select>
     </label>
     <label className="field">Period
      <select value={activePeriod} onChange={(e) => setStopPeriod(e.target.value)}>
       {availablePeriods.map((p) => <option key={p} value={p}>{p.replace('_', ' ')}</option>)}
      </select>
     </label>
    </div>}>
    {stopOptions.error ? <ErrorNotice error={stopOptions.error} />
     : stopForecast.error ? <ErrorNotice error={stopForecast.error} />
      : !stopForecast.data ? <Loading what="stop-period forecast" /> : <StopPeriodChart f={stopForecast.data} stale={stopForecast.loading} />}
   </Panel>

   <Panel title="Routes by forecast demand" note="Average forecast boardings per day over the horizon, against the last 28 observed days. The peak day is the busiest forecast day.">
    {!n ? <Loading /> : (
     <DataTable rows={n.by_route.slice(0, 30)} stale={network.loading} columns={[
      { key: 'route_id', label: 'Route', render: (r) => <Link to={`/routes/${r.route_id}`}>{String(r.route_id)}</Link> },
      { key: 'forecast_mean', label: 'Forecast / day', num: true, render: (r) => whole(Number(r.forecast_mean)) },
      { key: 'recent_28day_mean', label: 'Last 28 days / day', num: true, render: (r) => whole(Number(r.recent_28day_mean)) },
      { key: 'change_pct', label: 'Change', num: true, render: (r) => r.change_pct == null ? '-' : `${Number(r.change_pct) > 0 ? '+' : ''}${r.change_pct}%` },
      { key: 'peak_day', label: 'Peak day', render: (r) => shortDate(String(r.peak_day)) },
      { key: 'peak_value', label: 'Peak boardings', num: true, render: (r) => whole(Number(r.peak_value)) },
     ]} />
    )}
   </Panel>
  </div>
 )
}

function NetworkChart({ n }: { n: NetworkForecast }) {
 const rows = useMemo(() => [
  ...n.history.map((h) => ({ date: h.date, actual: h.actual, forecast: null as number | null })),
  ...n.forecast.map((f) => ({ date: f.date, actual: null as number | null, forecast: f.predicted })),
 ], [n])
 return (
  <ChartFrame rows={rows} legend={[{ label: 'Observed', slot: 0 }, { label: 'Forecast (estimate)', slot: 1 }]}
   columns={[{ key: 'date', label: 'Date' }, { key: 'actual', label: 'Observed', num: true, render: (r) => r.actual == null ? '' : whole(Number(r.actual)) },
    { key: 'forecast', label: 'Forecast', num: true, render: (r) => r.forecast == null ? '' : whole(Number(r.forecast)) }]}
   chart={<LinesChart data={rows} xKey="date" xFormat={shortDate} format={whole}
    series={[{ key: 'actual', label: 'Observed', slot: 0 }, { key: 'forecast', label: 'Forecast (estimate)', slot: 1 }]} />} />
 )
}

function RouteChart({ f, stale }: { f: RouteForecast; stale: boolean }) {
 const rows = useMemo(() => {
  const byDate = new Map<string, { date: string; actual: number | null; model: number | null; baseline: number | null }>()
  const at = (d: string) => byDate.get(d) ?? byDate.set(d, { date: d, actual: null, model: null, baseline: null }).get(d)!
  f.history.forEach((h) => { at(h.date).actual = h.actual })
  f.backtest.forEach((b) => { const r = at(b.date); r.model = b.predicted; r.baseline = b.baseline })
  f.forecast.forEach((p) => { at(p.date).model = p.predicted })
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
 }, [f])
 const m = f.backtest_errors.model, b = f.backtest_errors.baseline_28day
 return (
  <div style={{ opacity: stale ? 0.6 : 1 }}>
   <ChartFrame rows={rows} legend={[{ label: 'Observed', slot: 0 }, { label: 'Model (backtest, then forecast)', slot: 1 }, { label: '28-day baseline', slot: 2 }]}
    columns={[{ key: 'date', label: 'Date' },
     { key: 'actual', label: 'Observed', num: true, render: (r) => r.actual == null ? '' : whole(Number(r.actual)) },
     { key: 'model', label: 'Model', num: true, render: (r) => r.model == null ? '' : whole(Number(r.model)) },
     { key: 'baseline', label: 'Baseline', num: true, render: (r) => r.baseline == null ? '' : whole(Number(r.baseline)) }]}
    chart={<LinesChart data={rows} xKey="date" xFormat={shortDate} format={whole} height={300}
     series={[{ key: 'actual', label: 'Observed', slot: 0 }, { key: 'model', label: 'Model (backtest, then forecast)', slot: 1 }, { key: 'baseline', label: '28-day baseline', slot: 2 }]} />} />
   <DataTable rows={[
    { who: 'Model', mae: m.mae ?? null, rmse: m.rmse ?? null, mape: m.mape ?? null },
    { who: '28-day baseline', mae: b.mae ?? null, rmse: b.rmse ?? null, mape: b.mape ?? null },
   ]} caption={`Backtest error on route ${f.route_id}, test period`} columns={[
    { key: 'who', label: 'Test period, this route', sortable: false },
    { key: 'mae', label: 'MAE', num: true, sortable: false, render: (r) => whole(Number(r.mae)) },
    { key: 'rmse', label: 'RMSE', num: true, sortable: false, render: (r) => whole(Number(r.rmse)) },
    { key: 'mape', label: 'MAPE', num: true, sortable: false, render: (r) => r.mape == null ? '-' : `${r.mape}%` },
   ]} />
   <p className="panel-note">
    {m.mae != null && b.mae != null && (m.mae < b.mae
     ? <Status tone="good">The model beats the baseline on this route</Status>
     : <Status tone="warning">The baseline is better on this route</Status>)} {f.notes.join(' ')}
   </p>
  </div>
 )
}

function StopPeriodChart({ f, stale }: { f: StopPeriodForecast; stale: boolean }) {
 const rows = useMemo(() => [
  ...f.history.map((h) => ({ date: h.date, actual: h.actual, forecast: null as number | null })),
  ...f.forecast.map((p) => ({ date: p.date, actual: null as number | null, forecast: p.predicted })),
 ], [f])
 return (
  <div style={{ opacity: stale ? 0.6 : 1 }}>
   <ChartFrame rows={rows} legend={[{ label: 'Observed ticket tap-ins', slot: 0 }, { label: 'Forecast (estimate)', slot: 1 }]}
    columns={[{ key: 'date', label: 'Date' },
     { key: 'actual', label: 'Tap-ins', num: true, render: (r) => r.actual == null ? '' : whole(Number(r.actual)) },
     { key: 'forecast', label: 'Forecast', num: true, render: (r) => r.forecast == null ? '' : whole(Number(r.forecast)) }]}
    chart={<LinesChart data={rows} xKey="date" xFormat={shortDate} format={whole} height={260}
     series={[{ key: 'actual', label: 'Observed ticket tap-ins', slot: 0 }, { key: 'forecast', label: 'Forecast (estimate)', slot: 1 }]} />} />
   <p className="panel-note">Last observed day {shortDate(f.last_observed_date)}. {f.notes.join(' ')}</p>
  </div>
 )
}
