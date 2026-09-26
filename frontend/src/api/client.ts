/**
 * Thin fetch wrapper for the Flask API (/api/*, proxied by Vite to WSL:5000).
 *
 * - Adds the bearer token.
 * - Turns the backend's error envelope {error: {code, message, details}} into ApiError.
 * - Turns an explicit backend stub (HTTP 503 with `stub: true`) into StubUnavailable, so a
 *   page can fall back to clearly labelled sample data instead of showing an error.
 */

export type Row = Record<string, string | number | boolean | null>

export class ApiError extends Error {
  status: number
  code: string
  details?: Record<string, unknown>

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export class StubUnavailable extends Error {
  feature: string
  reason: string

  constructor(feature: string, reason: string) {
    super(reason)
    this.feature = feature
    this.reason = reason
  }
}

const TOKEN_KEY = 'utiq.token'

export const tokenStore = {
  get(): string | null {
    try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set(token: string | null) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token)
      else sessionStorage.removeItem(TOKEN_KEY)
    } catch { /* storage blocked: the session just won't survive a reload */ }
  },
}

let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(handler: () => void) { onUnauthorized = handler }

type Query = Record<string, string | number | undefined | null>

export function toQuery(params: Query = {}): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export async function api<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  let res: Response
  try {
    res = await fetch(`/api${path}${toQuery(init.query)}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the API. Start the backend with `flask run` inside WSL.')
  }

  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)

  if (res.status === 503 && body?.stub) throw new StubUnavailable(body.feature, body.reason)
  if (!res.ok) {
    const err = body?.error ?? {}
    if (res.status === 401 && token) onUnauthorized()
    throw new ApiError(res.status, err.code ?? 'http_error', err.message ?? `Request failed (${res.status}).`, err.details)
  }
  return body as T
}

/** Download a CSV export with the token (a plain <a href> cannot send the Authorization header). */
export async function downloadCsv(table: string, query: Query) {
  const token = tokenStore.get()
  const res = await fetch(`/api/reports/${table}.csv${toQuery(query)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.error?.code ?? 'http_error', body?.error?.message ?? 'Export failed.', body?.error?.details)
  }
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `${table}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
