/**
 * Session state: the signed-in user and their permissions.
 * The UI hides what a role cannot do, but the API enforces it; hiding is only convenience.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from '../api/client'
import type { LoginResponse, User } from '../api/types'

interface AuthState {
  user: User | null
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  can: (permission: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  const logout = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!tokenStore.get()) { setReady(true); return }
    api<{ user: User }>('/auth/me')
      .then((r) => setUser(r.user))
      .catch(() => tokenStore.set(null))
      .finally(() => setReady(true))
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    const r = await api<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
    tokenStore.set(r.access_token)
    setUser(r.user)
  }, [])

  const value = useMemo<AuthState>(() => ({
    user, ready, login, logout,
    can: (permission) => !!user?.permissions.includes(permission),
  }), [user, ready, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
