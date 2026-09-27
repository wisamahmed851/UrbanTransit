/**
 * Theme-aware CARTO basemaps for the network map. Dark Matter and Positron need no API key;
 * each is recoloured to the matching UrbanTransit IQ palette. If CARTO cannot be reached,
 * a self-contained background in the active theme keeps the transit network usable.
 */

import { setWorkerUrl, type StyleSpecification } from 'maplibre-gl'
// MapLibre 6 finds its worker next to its own file, which Vite's dependency pre-bundling
// moves. Let Vite bundle the worker (with its shared chunk) and hand MapLibre the URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)

export const CARTO_DARK_MATTER = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
export const CARTO_POSITRON = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
export type MapTheme = 'light' | 'dark'

/** Palette steps mirror the app's existing navy/blue tokens in each theme. */
export const MAP_COLORS: Record<MapTheme, Record<'land' | 'water' | 'roadMinor' | 'roadMajor' | 'boundary' | 'label' | 'labelHalo', string>> = {
 dark: {
  land: '#090d17', water: '#0b1640', roadMinor: '#1a1f2c', roadMajor: '#2d3242',
  boundary: '#414758', label: '#848c9f', labelHalo: '#090d17',
 },
 light: {
  land: '#f7f9ff', water: '#dce8f8', roadMinor: '#e3e8f2', roadMajor: '#c5cede',
  boundary: '#a8b2c2', label: '#565d70', labelHalo: '#f7f9ff',
 },
}

/** Offline fallback: plain themed ground, nothing fetched. Transit layers are added on top. */
function fallbackStyle(theme: MapTheme): StyleSpecification {
 return {
  version: 8,
  name: `UrbanTransit IQ ${theme} offline`,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': MAP_COLORS[theme].land } }],
 }
}

/** Repaint the CARTO style by layer role rather than relying on exact layer IDs. */
function recolor(style: StyleSpecification, theme: MapTheme): StyleSpecification {
 const colors = MAP_COLORS[theme]
 for (const layer of style.layers) {
  const id = layer.id.toLowerCase()
  const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {}
  if (layer.type === 'background') paint['background-color'] = colors.land
  else if (layer.type === 'fill' && id.includes('water')) paint['fill-color'] = colors.water
  else if (layer.type === 'fill') paint['fill-color'] = colors.land
  else if (layer.type === 'line' && id.includes('water')) paint['line-color'] = colors.water
  else if (layer.type === 'line' && /boundary|admin/.test(id)) paint['line-color'] = colors.boundary
  else if (layer.type === 'line' && /motorway|trunk|primary|major/.test(id)) paint['line-color'] = colors.roadMajor
  else if (layer.type === 'line') paint['line-color'] = colors.roadMinor
  else if (layer.type === 'symbol') {
   paint['text-color'] = colors.label
   paint['text-halo-color'] = colors.labelHalo
  }
  ;(layer as { paint?: Record<string, unknown> }).paint = paint
 }
 return style
}

export interface Basemap { style: StyleSpecification; offline: boolean; theme: MapTheme }

/** Fetch and recolour the active theme's CARTO map; use a matching fallback on failure. */
export async function loadBasemap(theme: MapTheme, timeoutMs = 4000): Promise<Basemap> {
 const ctrl = new AbortController()
 const timer = setTimeout(() => ctrl.abort(), timeoutMs)
 try {
  const url = theme === 'dark' ? CARTO_DARK_MATTER : CARTO_POSITRON
  const res = await fetch(url, { signal: ctrl.signal })
  if (!res.ok) throw new Error(`basemap ${res.status}`)
  return { style: recolor(await res.json(), theme), offline: false, theme }
 } catch {
  return { style: fallbackStyle(theme), offline: true, theme }
 } finally {
  clearTimeout(timer)
 }
}
