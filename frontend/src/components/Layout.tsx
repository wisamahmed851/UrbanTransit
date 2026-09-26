/**
 * App shell. Navigation is drawn as a transit line: pages are stations, the current page is
 * the filled stop. Pages still running on sample data sit on a dashed (hatched) track.
 */

import { Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Loading } from './ui'

interface Station { to: string; label: string; perm?: string }

const LINES: { title: string; kind?: 'sample'; stations: Station[] }[] = [
  {
    title: 'Network',
    stations: [
      { to: '/', label: 'Overview' },
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
const THEME_KEY = 'utiq.theme'

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem(THEME_KEY) as Theme) || 'system' } catch { return 'system' }
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
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <path d="M6 16h20" stroke="var(--accent-ink)" strokeWidth="3" strokeLinecap="round" />
      <circle cx="11" cy="16" r="4" fill="var(--accent)" stroke="var(--accent-ink)" strokeWidth="3" />
      <circle cx="22" cy="16" r="2.5" fill="var(--accent-ink)" />
    </svg>
  )
}

export function Layout() {
  const { user, logout, can } = useAuth()
  const [theme, setTheme] = useTheme()

  return (
    <div className="shell">
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
              <option value="system">Match system</option><option value="light">Light</option><option value="dark">Dark</option>
            </select>
          </label>
          <span>Signed in as <span className="who">{user?.username}</span> ({user?.roles.join(', ')})</span>
          <button className="btn btn-quiet" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main" id="main"><Suspense fallback={<Loading what="page" />}><Outlet /></Suspense></main>
    </div>
  )
}
