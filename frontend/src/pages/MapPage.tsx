/**
 * Network map: routes, stops and a replay of the 7-day GPS sample (10-16 Nov 2025).
 * It is a replay, never "live": the replay date and time are always on screen.
 */

import { ArrowsIn, Minus, Pause, Play, Plus } from '@phosphor-icons/react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Popup, type MapRef } from 'react-map-gl/maplibre'
import { useSearchParams } from 'react-router-dom'
import { loadBasemap, type Basemap } from '../components/map/basemap'
import { ROUTE_TYPES, TransitMap, type Geometry, type Picked, type RouteType, type Vehicle } from '../components/map/TransitMap'
import { RouteBadge, ErrorNotice, Loading } from '../components/ui'
import { label, num } from '../lib/format'
import { useApi } from '../lib/useApi'

interface ReplayWindow { start: string | null; end: string | null; days: { date: string; pings: number }[]; vehicles: number; source: string }
interface VehiclesResponse { at: string; active: number; vehicles: Vehicle[]; source: string }

const DAY_FMT = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
const SPEEDS = [{ v: 1, l: '1 min/s' }, { v: 5, l: '5 min/s' }, { v: 15, l: '15 min/s' }]
const FIRST_MINUTE = 5 * 60          // service runs about 05:30 to 23:30
const LAST_MINUTE = 23 * 60 + 59
const EVENT_LABEL: Record<string, string> = { stop_arrival: 'At a stop', stop_departure: 'Leaving a stop', in_transit: 'Between stops' }

const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
const dayLabel = (d: string) => DAY_FMT.format(new Date(`${d}T12:00:00`))

export function MapPage() {
  const mapRef = useRef<MapRef>(null)
  const [basemap, setBasemap] = useState<Basemap | null>(null)
  const geometry = useApi<Geometry>('/network/geometry')
  const replay = useApi<ReplayWindow>('/network/replay')

  const [types, setTypes] = useState<Set<RouteType>>(() => new Set(ROUTE_TYPES.map((t) => t.type)))
  // Replay moment and route live in the URL (?day=2025-11-12&t=08:15&route=R001), so a view can be shared.
  const [params, setParams] = useSearchParams()
  const setParam = useCallback((key: string, value: string | null) => setParams((p) => {
    const next = new URLSearchParams(p)
    if (value) next.set(key, value); else next.delete(key)
    return next
  }, { replace: true }), [setParams])
  const route = params.get('route') ?? ''
  const setRoute = (r: string) => setParam('route', r || null)
  const [showStops, setShowStops] = useState(true)
  const [picked, setPicked] = useState<Picked | null>(null)

  const chosenDay = params.get('day')
  const setDay = (d: string) => setParam('day', d)
  const fromUrl = /^(\d{2}):(\d{2})$/.exec(params.get('t') ?? '')
  const minute = fromUrl ? Math.min(LAST_MINUTE, Math.max(FIRST_MINUTE, Number(fromUrl[1]) * 60 + Number(fromUrl[2]))) : 8 * 60
  const setMinute = useCallback((m: number) => setParam('t', hhmm(m)), [setParam])
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(5)

  useEffect(() => { let live = true; loadBasemap().then((b) => live && setBasemap(b)); return () => { live = false } }, [])

  // Until a day is chosen, show the first full weekday of the sample, in the morning peak.
  const days = useMemo(() => replay.data?.days ?? [], [replay.data])
  const day = chosenDay ?? days[Math.min(2, days.length - 1)]?.date ?? null

  // Advance the replay clock while playing; stop at the end of the service day.
  const minuteRef = useRef(minute)
  useEffect(() => { minuteRef.current = minute }, [minute])
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      const next = minuteRef.current + speed
      if (next >= LAST_MINUTE) { setPlaying(false); setMinute(LAST_MINUTE) } else setMinute(next)
    }, 1000)
    return () => clearInterval(id)
  }, [playing, speed, setMinute])

  const at = day ? `${day}T${hhmm(minute)}:00` : null
  const vehicles = useApi<VehiclesResponse>(at ? '/network/vehicles' : null, { at: at ?? undefined })

  const routeOptions = useMemo(() => {
    const seen = new Map<string, { id: string; code: string; name: string; type: string }>()
    for (const f of geometry.data?.routes.features ?? []) {
      const p = f.properties
      if (!seen.has(String(p.route_id))) seen.set(String(p.route_id), { id: String(p.route_id), code: String(p.route_code), name: String(p.route_name), type: String(p.route_type) })
    }
    return [...seen.values()].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }))
  }, [geometry.data])

  const toggleType = (t: RouteType) => setTypes((s) => { const n = new Set(s); if (n.has(t)) n.delete(t); else n.add(t); return n })
  const resetView = () => mapRef.current?.flyTo({ center: [74.33, 31.52], zoom: 10.4, duration: 800 })
  const active = vehicles.data?.vehicles.filter((v) => types.has((v.route_type ?? 'local') as RouteType) && (!route || v.route_id === route)).length

  return (
    <div className="page map-page">
      <header className="page-head">
        <h1>Network map</h1>
        <p>All 118 routes and 756 stops. Bus positions replay the recorded 7-day GPS sample; there is no real-time feed.</p>
      </header>
      {(geometry.error || replay.error) && <ErrorNotice error={(geometry.error ?? replay.error)!} />}

      {!basemap ? <Loading what="map" /> : (
        <div className="map-shell" data-basemap={basemap.offline ? 'offline' : 'carto'}>
          <TransitMap ref={mapRef} basemap={basemap} geometry={geometry.data} vehicles={vehicles.data?.vehicles}
            types={types} route={route || null} showStops={showStops} onPick={setPicked}>
            {picked && <MapPopup picked={picked} day={day} onClose={() => setPicked(null)} />}
          </TransitMap>

          <form className="map-overlay map-filter" onSubmit={(e) => e.preventDefault()} aria-label="Map filters">
            <label className="field">Route
              <select value={route} onChange={(e) => setRoute(e.target.value)}>
                <option value="">All routes</option>
                {routeOptions.map((r) => <option key={r.id} value={r.id}>{r.code} ({r.name})</option>)}
              </select>
            </label>
            <fieldset>
              <legend>Route types</legend>
              {ROUTE_TYPES.map((t) => (
                <label className="check" key={t.type}>
                  <input type="checkbox" checked={types.has(t.type)} onChange={() => toggleType(t.type)} /> {t.label}
                </label>
              ))}
            </fieldset>
            <label className="check"><input type="checkbox" checked={showStops} onChange={(e) => setShowStops(e.target.checked)} /> Show stops</label>
          </form>

          <div className="map-overlay map-controls" role="group" aria-label="Zoom">
            <button type="button" aria-label="Zoom in" onClick={() => mapRef.current?.zoomIn()}><Plus size={18} weight="bold" aria-hidden="true" /></button>
            <button type="button" aria-label="Zoom out" onClick={() => mapRef.current?.zoomOut()}><Minus size={18} weight="bold" aria-hidden="true" /></button>
            <button type="button" aria-label="Show the whole network" onClick={resetView}><ArrowsIn size={18} weight="bold" aria-hidden="true" /></button>
          </div>

          <div className="map-overlay map-legend" aria-label="Legend">
            <h2 className="map-h">Legend</h2>
            {ROUTE_TYPES.map((t) => (
              <span className="legend-row" key={t.type}>
                <i className="legend-line" style={{ '--c': t.color } as React.CSSProperties} data-w={t.width} data-dashed={t.dashed || undefined} />{t.label} route
              </span>
            ))}
            <span className="legend-row"><i className="legend-ring" style={{ '--c': '#f5b301' } as React.CSSProperties} />Hub stop</span>
            <span className="legend-row"><i className="legend-ring" style={{ '--c': '#b6bdd1' } as React.CSSProperties} />Stop</span>
            <span className="legend-row"><i className="legend-dot" style={{ '--c': '#5181ff' } as React.CSSProperties} />Bus (gold on BRT)</span>
          </div>

          {basemap.offline && <p className="map-offline">Street map unavailable offline. Showing the network only.</p>}

          <div className="map-overlay map-replay" aria-label="GPS replay">
            <button type="button" className="btn" onClick={() => setPlaying((p) => !p)} disabled={!day}
              aria-label={playing ? 'Pause replay' : 'Play replay'}>
              {playing ? <Pause size={16} weight="fill" aria-hidden="true" /> : <Play size={16} weight="fill" aria-hidden="true" />}{playing ? 'Pause' : 'Play'}
            </button>
            <div>
              <div className="days" role="group" aria-label="Replay day">
                {days.map((d) => (
                  <button key={d.date} type="button" className="day-chip" aria-pressed={d.date === day} onClick={() => setDay(d.date)}>
                    {DAY_FMT.format(new Date(`${d.date}T12:00:00`)).replace(/ \d{4}$/, '')}
                  </button>
                ))}
                <select className="day-chip" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Replay speed">
                  {SPEEDS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
                </select>
              </div>
              <input type="range" min={FIRST_MINUTE} max={LAST_MINUTE} step={1} value={minute}
                onChange={(e) => setMinute(Number(e.target.value))} aria-label="Replay time" aria-valuetext={hhmm(minute)} />
            </div>
            <div className="replay-pill" aria-live="polite">
              <span className="pulse" data-paused={!playing || undefined} aria-hidden="true" />
              <span>
                {active ?? '-'} buses active
                <small>Replay of {day ? dayLabel(day) : '…'}, {hhmm(minute)}</small>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MapPopup({ picked, day, onClose }: { picked: Picked; day: string | null; onClose: () => void }) {
  return (
    <Popup longitude={picked.lng} latitude={picked.lat} anchor="bottom" offset={12} onClose={onClose}
      closeOnClick={false} className="map-popup" maxWidth="19rem">
      {picked.kind === 'vehicle' && (
        <>
          <h2 className="map-h">Bus {picked.props.vehicle_id} <RouteBadge code={picked.props.route_code} type={picked.props.route_type} id={picked.props.route_id} /></h2>
          <dl>
            <dt>Trip</dt><dd>{picked.props.trip_id ?? '-'}</dd>
            <dt>Status</dt><dd>{EVENT_LABEL[picked.props.event_type] ?? label(picked.props.event_type)}</dd>
            <dt>Speed</dt><dd>{picked.props.speed_kmh == null ? '-' : `${num(picked.props.speed_kmh, 1)} km/h`}</dd>
            <dt>Last ping</dt><dd>{picked.props.event_time.slice(11, 19)}</dd>
            <dt>Replay day</dt><dd>{day ? dayLabel(day) : '-'}</dd>
          </dl>
        </>
      )}
      {picked.kind === 'stop' && (
        <>
          <h2 className="map-h">{String(picked.props.stop_name)} ({String(picked.props.stop_id)})</h2>
          <dl>
            <dt>Type</dt><dd>{label(picked.props.stop_type)}</dd>
            <dt>Fare zone</dt><dd>{String(picked.props.zone)}</dd>
            <dt>Routes</dt><dd>{num(picked.props.routes_serving)}</dd>
            <dt>Buses per day</dt><dd>{num(picked.props.trips_serving_per_day)}</dd>
            <dt>Passengers per day (est.)</dt><dd>{num(picked.props.est_boardings_per_day)}</dd>
            <dt>Delay bottleneck</dt><dd>{picked.props.is_bottleneck ? 'Yes' : 'No'}</dd>
          </dl>
        </>
      )}
      {picked.kind === 'route' && (
        <>
          <h2 className="map-h"><RouteBadge code={picked.props.route_code} type={picked.props.route_type} id={picked.props.route_id} /> {String(picked.props.route_name)}</h2>
          <dl>
            <dt>Type</dt><dd>{label(picked.props.route_type)}</dd>
            <dt>Class</dt><dd>{String(picked.props.route_class ?? '-')}</dd>
            <dt>Composite score</dt><dd>{num(picked.props.composite_score, 1)}</dd>
            <dt>Boardings per day</dt><dd>{num(picked.props.med_daily_boardings)}</dd>
            <dt>Persistent overcrowding</dt><dd>{picked.props.overcrowded_flag ? 'Yes' : 'No'}</dd>
          </dl>
        </>
      )}
    </Popup>
  )
}

