import { useEffect, useState } from 'react'
import { loadBasemap, type Basemap, type MapTheme } from './basemap'

const QUERY = '(prefers-color-scheme: dark)'

/** Resolve explicit light/dark selection, or the OS preference when the app uses "system". */
function activeTheme(): MapTheme {
 const explicit = document.documentElement.getAttribute('data-theme')
 if (explicit === 'light' || explicit === 'dark') return explicit
 return window.matchMedia(QUERY).matches ? 'dark' : 'light'
}

/** Keep every map surface in sync with the app theme, including live OS-theme changes. */
export function useBasemap(): Basemap | null {
 const [theme, setTheme] = useState<MapTheme>(activeTheme)
 const [basemap, setBasemap] = useState<Basemap | null>(null)

 useEffect(() => {
  const media = window.matchMedia(QUERY)
  const update = () => setTheme(activeTheme())
  const observer = new MutationObserver(update)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  media.addEventListener('change', update)
  return () => { observer.disconnect(); media.removeEventListener('change', update) }
 }, [])

 useEffect(() => {
  let current = true
  loadBasemap(theme).then((next) => { if (current) setBasemap(next) })
  return () => { current = false }
 }, [theme])

 return basemap
}
