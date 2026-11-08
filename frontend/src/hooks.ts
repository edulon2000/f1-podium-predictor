import { useEffect, useState } from 'react'
import { get, NotFound } from './api'

export type Loadable<T> =
  | { state: 'loading' }
  | { state: 'missing' }
  | { state: 'error'; message: string }
  | { state: 'ready'; data: T }

/** Fetch a JSON endpoint; a 404 is reported as "missing" (an expected empty state). */
export function useApi<T>(path: string | null): Loadable<T> {
  const [value, setValue] = useState<Loadable<T>>({ state: 'loading' })
  useEffect(() => {
    if (path === null) return
    let alive = true
    setValue({ state: 'loading' })
    get<T>(path)
      .then((data) => alive && setValue({ state: 'ready', data }))
      .catch((err) => {
        if (!alive) return
        if (err instanceof NotFound) setValue({ state: 'missing' })
        else setValue({ state: 'error', message: String(err.message ?? err) })
      })
    return () => {
      alive = false
    }
  }, [path])
  return value
}

export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return now
}
