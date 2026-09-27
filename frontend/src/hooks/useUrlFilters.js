import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useDebouncedValue } from './useDebouncedValue'

/**
 * List state kept in the URL query string (filters, ordering, page), so refresh, the Back button
 * and shared links all show the same view. Used by every list page.
 *
 *   const list = useUrlFilters(['search', 'status'], { ordering: '-created_at', defaults: { status: 'OPEN' } })
 *   list.values.status, list.ordering, list.page
 *   list.update({ status: 'RESOLVED' })            // also returns to page 1
 *   list.searchText / list.setSearchText           // debounced into ?search=
 *   list.queryKey                                  // changes whenever the URL does (use as a loader dependency)
 *
 * `defaults` apply when a key is absent from the URL. Choosing "All" stores an explicit empty value
 * (?status=) so it is not replaced by the default again.
 */
export function useUrlFilters(keys, { ordering: defaultOrdering = '', defaults = {} } = {}) {
  const [params, setParams] = useSearchParams()
  const values = Object.fromEntries(keys.map((key) => [key, params.has(key) ? params.get(key) : (defaults[key] ?? '')]))
  const ordering = params.get('ordering') || defaultOrdering
  const page = Number(params.get('page')) || 1

  const update = useCallback((changes, { resetPage = true } = {}) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      Object.entries(changes).forEach(([key, value]) => {
        if (value) next.set(key, value)
        else if (key in defaults) next.set(key, '')   // keep "All" instead of falling back to the default
        else next.delete(key)
      })
      if (resetPage) next.delete('page')
      return next
    }, { replace: true })
    // `defaults` is a literal at the call site; its keys are what matters and they never change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setParams])

  // Typing in a search box updates the URL only after a short pause.
  const [searchText, setSearchText] = useState(values.search || '')
  const debouncedSearch = useDebouncedValue(searchText)
  useEffect(() => {
    if (keys.includes('search') && debouncedSearch !== (params.get('search') || '')) update({ search: debouncedSearch })
  }, [debouncedSearch, keys, params, update])

  const clear = useCallback(() => {
    setSearchText('')
    setParams(new URLSearchParams(), { replace: true })
  }, [setParams])

  return { values, ordering, page, update, clear, searchText, setSearchText, queryKey: params.toString() }
}

/** Rebuild API parameters from a queryKey (inside a useCallback loader). */
export function paramsFrom(queryKey, keys, { ordering = '', defaults = {}, pageSize = 20 } = {}) {
  const current = new URLSearchParams(queryKey)
  return {
    ...Object.fromEntries(keys.map((key) => [key, current.has(key) ? current.get(key) : (defaults[key] ?? '')])),
    ordering: current.get('ordering') || ordering,
    page: current.get('page') || 1,
    page_size: pageSize,
  }
}
