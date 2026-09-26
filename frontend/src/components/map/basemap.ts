/**
 * Basemap for the network map: CARTO Dark Matter (free vector style, no API key),
 * recoloured to the navy palette. When the style cannot be fetched (offline, blocked,
 * CARTO down), a self-contained navy style is used instead so the transit network still
 * renders on its own. The fallback makes no network requests.
 */

import { setWorkerUrl, type StyleSpecification } from 'maplibre-gl'
// MapLibre 6 finds its worker next to its own file, which Vite's dependency pre-bundling
// moves. Let Vite bundle the worker (with its shared chunk) and hand MapLibre the URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)

export const CARTO_DARK_MATTER = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/** Navy palette steps used on the map (ui-color-palette, CMD-022). */
export const MAP_COLORS = {
  land: '#090d17',      // navy-950
  water: '#0b1640',     // navy-950 mixed toward blue-800
  roadMinor: '#1a1f2c', // navy-900
  roadMajor: '#2d3242', // navy-800
  boundary: '#414758',  // navy-700
  label: '#848c9f',     // navy-400
  labelHalo: '#090d17',
}

/** Offline fallback: plain navy ground, nothing fetched. Transit layers are added on top. */
export const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  name: 'UrbanTransit IQ offline',
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': MAP_COLORS.land } }],
}

/** Repaint Dark Matter's layers in the navy palette (by layer role, not by exact id). */
function recolor(style: StyleSpecification): StyleSpecification {
  for (const layer of style.layers) {
    const id = layer.id.toLowerCase()
    const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {}
    if (layer.type === 'background') paint['background-color'] = MAP_COLORS.land
    else if (layer.type === 'fill' && id.includes('water')) paint['fill-color'] = MAP_COLORS.water
    else if (layer.type === 'fill') paint['fill-color'] = MAP_COLORS.land
    else if (layer.type === 'line' && id.includes('water')) paint['line-color'] = MAP_COLORS.water
    else if (layer.type === 'line' && /boundary|admin/.test(id)) paint['line-color'] = MAP_COLORS.boundary
    else if (layer.type === 'line' && /motorway|trunk|primary|major/.test(id)) paint['line-color'] = MAP_COLORS.roadMajor
    else if (layer.type === 'line') paint['line-color'] = MAP_COLORS.roadMinor
    else if (layer.type === 'symbol') {
      paint['text-color'] = MAP_COLORS.label
      paint['text-halo-color'] = MAP_COLORS.labelHalo
    }
    ;(layer as { paint?: Record<string, unknown> }).paint = paint
  }
  return style
}

export interface Basemap { style: StyleSpecification; offline: boolean }

/** Fetch and recolour Dark Matter; fall back to the navy style after `timeoutMs` or any failure. */
export async function loadBasemap(timeoutMs = 4000): Promise<Basemap> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(CARTO_DARK_MATTER, { signal: ctrl.signal })
    if (!res.ok) throw new Error(`basemap ${res.status}`)
    return { style: recolor(await res.json()), offline: false }
  } catch {
    return { style: FALLBACK_STYLE, offline: true }
  } finally {
    clearTimeout(timer)
  }
}
