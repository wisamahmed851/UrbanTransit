/**
 * The transit network on a MapLibre map: route lines, stops and (optionally) buses.
 *
 * Route types share one colour family and are told apart by weight and dash, never by a new
 * hue (colour lock): BRT = thick gold with a soft glow, trunk = blue, local = thin light blue,
 * feeder = dashed grey. Hub stops get a gold ring. The map is always dark, in both themes,
 * because the basemap is.
 *
 * Our sources and layers are added imperatively on `style.load` (the style definition is
 * parsed; tiles and fonts may still be loading) and fed with `setData` / `setFilter`.
 * The declarative react-map-gl <Source>/<Layer> children wait for the whole basemap to load,
 * which on a slow network or CPU left the buses and the overview's route lines empty (CMD-022).
 */

import 'maplibre-gl/dist/maplibre-gl.css'
import type { ExpressionSpecification, FilterSpecification, GeoJSONSource, LayerSpecification, Map as MlMap } from 'maplibre-gl'
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react'
import Map, { type MapLayerMouseEvent, type MapRef } from 'react-map-gl/maplibre'
import type { FeatureCollection, LineString, Point } from 'geojson'
import type { Basemap } from './basemap'

export type RouteType = 'brt' | 'trunk' | 'local' | 'feeder'
export const ROUTE_TYPES: { type: RouteType; label: string; color: string; width: number; dashed?: boolean }[] = [
  { type: 'brt', label: 'BRT', color: '#f5b301', width: 5 },
  { type: 'trunk', label: 'Trunk', color: '#5181ff', width: 3 },
  { type: 'local', label: 'Local', color: '#6a9cff', width: 2 },
  { type: 'feeder', label: 'Feeder', color: '#9da4b8', width: 2, dashed: true },
]

export interface Geometry {
  routes: FeatureCollection<LineString, Record<string, string | number | boolean | null>>
  stops: FeatureCollection<Point, Record<string, string | number | boolean | null>>
}

export interface Vehicle {
  vehicle_id: string; trip_id: string | null; route_id: string | null; route_code: string | null
  route_type: RouteType | null; stop_id: string | null; event_type: string; event_time: string
  longitude: number; latitude: number; speed_kmh: number | null
}

export type Picked =
  | { kind: 'vehicle'; lng: number; lat: number; props: Vehicle }
  | { kind: 'stop' | 'route'; lng: number; lat: number; props: Record<string, unknown> }

interface Props {
  basemap: Basemap
  geometry: Geometry | null
  vehicles?: Vehicle[]
  types: Set<RouteType>
  route?: string | null
  showStops?: boolean
  interactive?: boolean
  /** Starting zoom; the full network needs about 10.4 on a tall map, less on a short strip. */
  zoom?: number
  onPick?: (p: Picked | null) => void
  children?: React.ReactNode
}

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }
const NO_VEHICLES: Vehicle[] = []
const PICKABLE = ['vehicles', 'stops', 'stops-hub', 'routes', 'routes-feeder']
const expr = (e: unknown) => e as ExpressionSpecification
const filt = (e: unknown) => e as FilterSpecification

const WIDTH_BY_TYPE = expr(['match', ['get', 'route_type'], 'brt', 5, 'trunk', 3, 2])
const ZOOM_R = (lo: number, hi: number) => expr(['interpolate', ['linear'], ['zoom'], 10, lo, 14, hi])

/** Layer definitions in draw order (bottom to top); filters are set separately. */
const LAYERS: LayerSpecification[] = [
  { id: 'routes-casing', type: 'line', source: 'routes', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#090d17', 'line-width': expr(['+', WIDTH_BY_TYPE, 2]), 'line-opacity': 0.7 } },
  { id: 'routes-glow', type: 'line', source: 'routes', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#f5b301', 'line-width': 12, 'line-blur': 8, 'line-opacity': 0.28 } },
  { id: 'routes', type: 'line', source: 'routes', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': expr(['match', ['get', 'route_type'], 'brt', '#f5b301', 'trunk', '#5181ff', 'local', '#6a9cff', '#9da4b8']),
      'line-width': WIDTH_BY_TYPE, 'line-opacity': 0.85 } },
  { id: 'routes-feeder', type: 'line', source: 'routes',
    paint: { 'line-color': '#9da4b8', 'line-width': 2, 'line-dasharray': [2, 1.6], 'line-opacity': 0.9 } },
  { id: 'stops', type: 'circle', source: 'stops', filter: filt(['!=', ['get', 'stop_type'], 'hub']),
    paint: { 'circle-radius': ZOOM_R(1.8, 5), 'circle-color': '#090d17', 'circle-stroke-color': '#b6bdd1', 'circle-stroke-width': 1 } },
  { id: 'stops-hub', type: 'circle', source: 'stops', filter: filt(['==', ['get', 'stop_type'], 'hub']),
    paint: { 'circle-radius': ZOOM_R(3.5, 8), 'circle-color': '#090d17', 'circle-stroke-color': '#f5b301', 'circle-stroke-width': 2 } },
  { id: 'vehicles', type: 'circle', source: 'vehicles',
    paint: { 'circle-radius': ZOOM_R(3.5, 7), 'circle-stroke-color': '#ebf2ff', 'circle-stroke-width': 1.5,
      'circle-color': expr(['match', ['get', 'route_type'], 'brt', '#f5b301', 'feeder', '#9da4b8', '#5181ff']) } },
]

/** Add our sources and layers once the style definition is in (idempotent). */
function install(map: MlMap) {
  for (const id of ['routes', 'stops', 'vehicles']) if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY })
  for (const layer of LAYERS) if (!map.getLayer(layer.id)) map.addLayer(layer)
}

export const TransitMap = forwardRef<MapRef, Props>(function TransitMap(
  { basemap, geometry, vehicles = NO_VEHICLES, types, route = null, showStops = true, interactive = true, zoom = 10.4, onPick, children }, ref,
) {
  const mapRef = useRef<MapRef>(null)
  useImperativeHandle(ref, () => mapRef.current as MapRef, [])
  const [ready, setReady] = useState(false)
  const [cursor, setCursor] = useState('')

  // Install our layers as soon as the style definition is parsed ('styledata' fires then,
  // long before tiles and fonts finish). install() is idempotent, so repeat events are harmless.
  const onStyleData = (e: { target: MlMap }) => {
    const map = e.target
    if (!(map as unknown as { style?: { _loaded?: boolean } }).style?._loaded) return
    install(map)
    if (!ready) setReady(true)
  }

  // Data.
  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!ready || !map) return
    ;(map.getSource('routes') as GeoJSONSource).setData(geometry?.routes ?? EMPTY)
    ;(map.getSource('stops') as GeoJSONSource).setData(showStops && geometry ? geometry.stops : EMPTY)
  }, [ready, geometry, showStops])

  const vehicleGeo = useMemo<FeatureCollection<Point>>(() => ({
    type: 'FeatureCollection',
    features: vehicles.map((v) => ({ type: 'Feature', properties: { ...v }, geometry: { type: 'Point', coordinates: [v.longitude, v.latitude] } })),
  }), [vehicles])

  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (ready && map) (map.getSource('vehicles') as GeoJSONSource).setData(vehicleGeo)
  }, [ready, vehicleGeo])

  // Filters: route type toggles and the single-route selection.
  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!ready || !map) return
    const typeList = [...types]
    const byType = ['in', ['get', 'route_type'], ['literal', typeList]]
    const byRoute = route ? ['==', ['get', 'route_id'], route] : ['has', 'route_id']
    const lines = ['all', byType, byRoute]
    map.setFilter('routes-casing', filt(lines))
    map.setFilter('routes-glow', filt(['all', lines, ['==', ['get', 'route_type'], 'brt']]))
    map.setFilter('routes', filt(['all', lines, ['!=', ['get', 'route_type'], 'feeder']]))
    map.setFilter('routes-feeder', filt(['all', lines, ['==', ['get', 'route_type'], 'feeder']]))
    map.setFilter('vehicles', filt(['all', ['in', ['coalesce', ['get', 'route_type'], 'local'], ['literal', typeList]], byRoute]))
    map.setPaintProperty('routes', 'line-opacity', route ? 1 : 0.85)
  }, [ready, types, route])

  const pick = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0]
    if (!onPick) return
    if (!f) { onPick(null); return }
    const { lng, lat } = e.lngLat
    const layer = f.layer.id
    if (layer === 'vehicles') {
      const v = vehicles.find((x) => x.vehicle_id === f.properties.vehicle_id)
      if (v) onPick({ kind: 'vehicle', lng, lat, props: v })
    } else if (layer.startsWith('stops')) onPick({ kind: 'stop', lng, lat, props: f.properties })
    else onPick({ kind: 'route', lng, lat, props: f.properties })
  }

  return (
    <Map
      ref={mapRef}
      initialViewState={{ longitude: 74.33, latitude: 31.52, zoom }}
      mapStyle={basemap.style}
      attributionControl={basemap.offline ? false : { compact: true }}
      interactive={interactive}
      style={{ width: '100%', height: '100%' }}
      cursor={cursor}
      interactiveLayerIds={interactive && ready ? PICKABLE : []}
      onStyleData={onStyleData}
      onClick={pick}
      onMouseEnter={() => setCursor('pointer')}
      onMouseLeave={() => setCursor('')}
    >
      {children}
    </Map>
  )
})
