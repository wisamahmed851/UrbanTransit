import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { User } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { DataTable } from '../../components/DataTable'
import { ErrorNotice, Loading, PageHead, Panel, Status } from '../../components/ui'
import { useApi } from '../../lib/useApi'

const ROLES = ['admin', 'operator', 'analyst', 'evaluator']
const ROLE_ABOUT: Record<string, string> = {
  admin: 'everything, including users and reference data',
  operator: 'dashboards, exports, predictions, recommendations',
  analyst: 'dashboards, exports, model results',
  evaluator: 'read-only results plus the audit log',
}

export function UsersPage() {
  const { user: me } = useAuth()
  const users = useApi<{ users: User[] }>('/admin/users')
  const [form, setForm] = useState({ username: '', email: '', password: '', roles: ['analyst'] })
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api('/admin/users', { method: 'POST', body: JSON.stringify({ ...form, email: form.email || null }) })
      setForm({ username: '', email: '', password: '', roles: ['analyst'] })
      users.reload()
    } catch (err) { setError(err as ApiError) } finally { setBusy(false) }
  }

  const update = async (u: User, patch: Partial<User>) => {
    setError(null)
    try { await api(`/admin/users/${u.id}`, { method: 'PATCH', body: JSON.stringify(patch) }); users.reload() }
    catch (err) { setError(err as ApiError) }
  }

  return (
    <div className="page">
      <PageHead title="Users">Accounts and what each role may do. Changes apply on the user's next click, not at their next sign-in.</PageHead>
      {error && <ErrorNotice error={error} />}

      <Panel title="Add a user">
        <form onSubmit={create} style={{ display: 'grid', gap: '0.9rem' }}>
          <div className="filters">
            <label className="field">Username<input required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></label>
            <label className="field">Email (optional)<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label className="field">Password<input type="password" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          </div>
          <fieldset style={{ border: 0, padding: 0, margin: 0, display: 'grid', gap: '0.3rem' }}>
            <legend style={{ fontSize: 'var(--fs-sm)', color: 'var(--ink-2)', marginBottom: '0.3rem' }}>Roles</legend>
            {ROLES.map((r) => (
              <label key={r} style={{ fontSize: 'var(--fs-sm)', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input type="checkbox" checked={form.roles.includes(r)}
                  onChange={(e) => setForm({ ...form, roles: e.target.checked ? [...form.roles, r] : form.roles.filter((x) => x !== r) })} />
                <b>{r}</b> <span style={{ color: 'var(--ink-muted)' }}>{ROLE_ABOUT[r]}</span>
              </label>
            ))}
          </fieldset>
          <div><button className="btn" type="submit" disabled={busy || !form.roles.length}>Add user</button></div>
        </form>
      </Panel>

      <Panel title="Accounts">
        {users.error ? <ErrorNotice error={users.error} /> : !users.data ? <Loading what="users" /> : (
          <DataTable rows={users.data.users as never} columns={[
            { key: 'username', label: 'Username' },
            { key: 'email', label: 'Email' },
            { key: 'roles', label: 'Role', sortable: false, render: (r) => {
              const u = r as unknown as User
              return (
                <select aria-label={`Role for ${u.username}`} value={u.roles[0] ?? ''} disabled={u.id === me?.id}
                  onChange={(e) => update(u, { roles: [e.target.value] })}>
                  {ROLES.map((x) => <option key={x}>{x}</option>)}
                </select>
              )
            } },
            { key: 'is_active', label: 'Status', render: (r) => (r.is_active ? <Status tone="good">Active</Status> : <Status tone="neutral">Deactivated</Status>) },
            { key: 'last_login_at', label: 'Last sign-in', render: (r) => (r.last_login_at ? String(r.last_login_at).replace('T', ' ').slice(0, 16) : 'Never') },
            { key: '_act', label: '', sortable: false, render: (r) => {
              const u = r as unknown as User
              return u.id === me?.id ? <span style={{ color: 'var(--ink-muted)' }}>You</span> : (
                <button className="btn btn-quiet" type="button" onClick={() => update(u, { is_active: !u.is_active })}>
                  {u.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
              )
            } },
          ]} />
        )}
      </Panel>
    </div>
  )
}
