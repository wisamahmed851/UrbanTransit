/**
 * Fetch hook with "hold the previous result while refetching" (no skeleton flash when a
 * filter changes) and an explicit stub state for endpoints whose data does not exist yet.
 */

import { useEffect, useRef, useState } from 'react'
import { api, ApiError, StubUnavailable, type Row } from '../api/client'
import type { RowsResponse } from '../api/types'

export interface ApiState<T> {
  data: T | null
  error: ApiError | null
  stub: StubUnavailable | null
  loading: boolean
  reload: () => void
}

export function useApi<T>(path: string | null, query?: Record<string, string | number | undefined | null>): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [stub, setStub] = useState<StubUnavailable | null>(null)
  const [loading, setLoading] = useState(!!path)
  const [tick, setTick] = useState(0)
  // The effect is keyed on the serialized request, so callers can pass inline query objects
  // without triggering a refetch on every render.
  const key = JSON.stringify([path, query, tick])
  const latest = useRef(key)

  useEffect(() => {
    if (!path) return
    latest.current = key
    setLoading(true)
    api<T>(path, { query })
      .then((d) => { if (latest.current === key) { setData(d); setError(null); setStub(null) } })
      .catch((e) => {
        if (latest.current !== key) return
        if (e instanceof StubUnavailable) setStub(e)
        else setError(e instanceof ApiError ? e : new ApiError(0, 'error', String(e)))
      })
      .finally(() => { if (latest.current === key) setLoading(false) })
  }, [key])

  return { data, error, stub, loading, reload: () => setTick((t) => t + 1) }
}

/** Rows of one analytics table, e.g. useRows('route_performance', {sort: '-composite_score', limit: 10}). */
export function useRows<R = Row>(table: string, query?: Record<string, string | number | undefined | null>) {
  return useApi<RowsResponse<R>>(`/analytics/${table}`, query)
}

/**
 * Every matching row of an analytics table, fetched 1,000 at a time (the API page cap).
 * Only for tables of a few thousand rows where the page needs complete counts.
 */
export function useAllRows<R = Row>(table: string, query: Record<string, string | undefined> = {}) {
  const [rows, setRows] = useState<R[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const key = JSON.stringify([table, query])
  const latest = useRef(key)

  useEffect(() => {
    latest.current = key
    let cancelled = false
    ;(async () => {
      const out: R[] = []
      for (let offset = 0; ; offset += 1000) {
        const page = await api<RowsResponse<R>>(`/analytics/${table}`, { query: { ...query, limit: 1000, offset } })
        out.push(...page.rows)
        if (offset + 1000 >= page.total) break
      }
      return out
    })()
      .then((r) => { if (!cancelled && latest.current === key) { setRows(r); setError(null) } })
      .catch((e) => { if (!cancelled) setError(e instanceof ApiError ? e : new ApiError(0, 'error', String(e))) })
    return () => { cancelled = true }
  }, [key])

  return { rows, error, loading: rows === null && !error }
}
