import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useState } from 'react'
import Map, { Layer, Source } from 'react-map-gl/maplibre'
import type { FeatureCollection, Point } from 'geojson'
import { loadBasemap, type Basemap } from '../components/map/basemap'
import { ErrorNotice, Loading, PageHead } from '../components/ui'
import { useApi } from '../lib/useApi'

interface StopRow { stop_id: string; stop_name: string; latitude: number; longitude: number; stop_type: string }

export function MapPage() {
  const [basemap, setBasemap] = useState<Basemap | null>(null)
  const stops = useApi<{ rows: StopRow[] }>('/admin/stops', { limit: 1000 })

  useEffect(() => { let live = true; loadBasemap().then((b) => live && setBasemap(b)); return () => { live = false } }, [])

  const stopsGeo = useMemo<FeatureCollection<Point>>(() => ({
    type: 'FeatureCollection',
    features: (stops.data?.rows ?? []).map((s) => ({
      type: 'Feature', properties: { id: s.stop_id, name: s.stop_name, type: s.stop_type },
      geometry: { type: 'Point', coordinates: [s.longitude, s.latitude] },
    })),
  }), [stops.data])

  return (
    <div className="page">
      <PageHead title="Network map" />
      {stops.error && <ErrorNotice error={stops.error} />}
      {!basemap ? <Loading what="map" /> : (
        <div className="map-shell" data-basemap={basemap.offline ? 'offline' : 'carto'}>
          <Map initialViewState={{ longitude: 74.33, latitude: 31.52, zoom: 10.6 }} mapStyle={basemap.style}
            attributionControl={basemap.offline ? false : { compact: true }} style={{ width: '100%', height: '100%' }}>
            <Source id="stops" type="geojson" data={stopsGeo}>
              <Layer id="stops" type="circle" paint={{ 'circle-radius': 3, 'circle-color': '#5181ff', 'circle-stroke-color': '#ebf2ff', 'circle-stroke-width': 1 }} />
            </Source>
          </Map>
          {basemap.offline && <p className="map-offline">Street map unavailable offline. Showing the network only.</p>}
        </div>
      )}
    </div>
  )
}
