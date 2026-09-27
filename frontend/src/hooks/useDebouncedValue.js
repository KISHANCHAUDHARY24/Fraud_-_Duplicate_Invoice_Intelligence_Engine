import { useEffect, useState } from 'react'

/** The value, but only after it has stopped changing for `delay` ms (e.g. search-as-you-type). */
export function useDebouncedValue(value, delay = 350) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}
