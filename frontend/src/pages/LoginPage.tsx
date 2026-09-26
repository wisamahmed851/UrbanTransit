import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { BrandMark } from '../components/Layout'
import { ErrorNotice } from '../components/ui'

/** A schematic of four lines (BRT, trunk, local, feeder) that draws itself once on load. */
function NetworkArt() {
  const lines = [
    { d: 'M10 150 H120 L160 110 H300 L340 70 H470', w: 6 },
    { d: 'M40 40 L110 110 H200 L250 160 H420', w: 4 },
    { d: 'M190 20 V90 L230 130 V200', w: 3 },
    { d: 'M300 190 L340 150 H400 L440 110', w: 3 },
  ]
  const stops = [[120, 150], [160, 110], [300, 110], [340, 70], [110, 110], [200, 110], [250, 160], [190, 90], [230, 130], [340, 150], [400, 150]]
  return (
    <svg className="art" viewBox="0 0 480 210" role="img" aria-label="Schematic map of bus lines">
      <style>{`
        .art-line { fill: none; stroke: var(--accent-ink); stroke-linecap: round; stroke-linejoin: round; opacity: .9;
          stroke-dasharray: 700; stroke-dashoffset: 700; animation: draw 1.6s cubic-bezier(.6,.1,.2,1) forwards; }
        .art-line:nth-child(2) { animation-delay: .15s } .art-line:nth-child(3) { animation-delay: .3s } .art-line:nth-child(4) { animation-delay: .45s }
        .art-stop { fill: var(--accent); stroke: var(--accent-ink); stroke-width: 3; opacity: 0; animation: pop .3s 1.2s forwards; }
        @keyframes draw { to { stroke-dashoffset: 0 } }
        @keyframes pop { to { opacity: 1 } }
        @media (prefers-reduced-motion: reduce) { .art-line { stroke-dashoffset: 0; animation: none } .art-stop { opacity: 1; animation: none } }
      `}</style>
      {lines.map((l) => <path key={l.d} className="art-line" d={l.d} strokeWidth={l.w} />)}
      {stops.map(([x, y]) => <circle key={`${x}-${y}`} className="art-stop" cx={x} cy={y} r="6" />)}
    </svg>
  )
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={from} replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'error', String(err)))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login-art">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 800 }}>
          <BrandMark /> UrbanTransit IQ
        </div>
        <NetworkArt />
        <div style={{ display: 'grid', gap: '0.9rem' }}>
          <h1>Know which routes need you today.</h1>
          <p>Route scores, delays, crowding and passenger flows for 118 routes and 756 stops, from a year of trip, counter and smart-card data.</p>
        </div>
      </section>
      <section className="login-form">
        <h2>Sign in</h2>
        <form onSubmit={submit}>
          <label className="field">Username
            <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </label>
          <label className="field">Password
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <ErrorNotice error={error} />}
          <button className="btn" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-muted)', maxWidth: '36ch' }}>
          No account yet? An admin creates one with <code>flask users create</code>.
        </p>
      </section>
    </div>
  )
}
