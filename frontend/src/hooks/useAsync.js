import { useCallback, useEffect, useState } from 'react'

/**
 * Run an async loader and expose { data, error, loading, reload }: the three states every page shows.
 *
 * Pass a STABLE loader: a module-level function, or one wrapped in useCallback with its
 * dependencies, so it re-runs exactly when those values change:
 *     const load = useCallback(() => fetchInvoices(filters), [filters])
 *     const { data, loading, error, reload } = useAsync(load)
 *
 * `loading` is derived (the result belongs to an older loader or attempt), not set inside the
 * effect. While reloading, the previous data stays on screen.
 */
export function useAsync(loader) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ loader: null, attempt: -1, data: null, error: null })

  useEffect(() => {
    let active = true
    loader().then(
      (data) => active && setResult({ loader, attempt, data, error: null }),
      (error) => active && setResult({ loader, attempt, data: null, error }),
    )
    return () => {
      active = false
    }
  }, [loader, attempt])

  const reload = useCallback(() => setAttempt((value) => value + 1), [])
  const loading = result.loader !== loader || result.attempt !== attempt
  return { data: result.data, error: result.error, loading, reload }
}
