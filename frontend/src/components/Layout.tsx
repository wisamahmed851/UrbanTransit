/**
 * App shell. Navigation is drawn as a transit line: pages are stations, the current page is
 * the filled stop. Pages still running on sample data sit on a dashed (hatched) track.
 */

import { Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { StaggerScope } from './motion'
import { Loading } from './ui'

interface Station { to: string; label: string; perm?: string }

const LINES: { title: string; kind?: 'sample'; stations: Station[] }[] = [
  {
    title: 'Network',
    stations: [
      { to: '/', label: 'Overview' },
      { to: '/map', label: 'Network map' },
      { to: '/routes', label: 'Routes' },
      { to: '/delays', label: 'Delays' },
      { to: '/crowding', label: 'Crowding and capacity' },
      { to: '/stops', label: 'Stops' },
      { to: '/demand', label: 'Demand and journeys' },
      { to: '/passengers', label: 'Passengers' },
    ],
  },
  {
    title: 'Evidence',
    stations: [
      { to: '/models', label: 'Model results', perm: 'models:read' },
      { to: '/explorer', label: 'Data explorer' },
    ],
  },
  {
    title: 'Coming with Phase 7',
    kind: 'sample',
    stations: [
      { to: '/predictions', label: 'Predictions', perm: 'predictions:use' },
      { to: '/recommendations', label: 'Recommendations', perm: 'recommendations:read' },
    ],
  },
  {
    title: 'Administration',
    stations: [
      { to: '/admin/reference', label: 'Routes, stops, vehicles', perm: 'reference:read' },
      { to: '/admin/users', label: 'Users', perm: 'users:manage' },
      { to: '/admin/audit', label: 'Audit log', perm: 'audit:read' },
    ],
  },
]

type Theme = 'system' | 'light' | 'dark'
export const THEME_KEY = 'utiq.theme'
/** Dark is the brand's default; viewers can switch to light or follow the OS. */
export const DEFAULT_THEME: Theme = 'dark'

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem(THEME_KEY) as Theme) || DEFAULT_THEME } catch { return DEFAULT_THEME }
  })
  useEffect(() => {
    if (theme === 'system') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem(THEME_KEY, theme) } catch { /* per-viewer convenience only */ }
  }, [theme])
  return [theme, setTheme]
}

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#274dcf" />
      <path d="M6 16h20" stroke="#ebf2ff" strokeWidth="3" strokeLinecap="round" />
      <circle cx="11" cy="16" r="4" fill="#274dcf" stroke="#ebf2ff" strokeWidth="3" />
      <circle cx="22" cy="16" r="3" fill="#f5b301" />
    </svg>
  )
}

export function Layout() {
  const { user, logout, can } = useAuth()
  const [theme, setTheme] = useTheme()
  const { pathname } = useLocation()

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <aside className="line-nav">
        <Link to="/" className="brand">
          <BrandMark />
          <span className="brand-name">UrbanTransit IQ<small>Bus network analytics</small></span>
        </Link>
        <nav aria-label="Main">
          {LINES.map((line) => {
            const stations = line.stations.filter((s) => !s.perm || can(s.perm))
            if (!stations.length) return null
            return (
              <div key={line.title}>
                <p className="line-group-title">{line.title}</p>
                <ul className="line-group" data-kind={line.kind}>
                  {stations.map((s) => (
                    <li key={s.to}>
                      <NavLink to={s.to} end={s.to === '/'} className="station">{s.label}</NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </nav>
        <div className="nav-foot">
          <label className="field">Theme
            <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
              <option value="dark">Dark</option><option value="light">Light</option><option value="system">Match system</option>
            </select>
          </label>
          <span>Signed in as <span className="who">{user?.username}</span> ({user?.roles.join(', ')})</span>
          <button className="btn btn-quiet" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main" id="main"><Suspense fallback={<Loading what="page" />}><StaggerScope key={pathname}><Outlet /></StaggerScope></Suspense></main>
    </div>
  )
}
