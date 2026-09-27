/** Small building blocks for the filter bar above every list (same look on every page). */
import { Search, X } from 'lucide-react'

import Button from './Button'

export const FILTER_INPUT = 'h-9 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none'

export function FilterField({ label, children, className = '' }) {
  return (
    <label className={`block text-xs font-medium text-slate-500 ${className}`}>
      {label}
      <div className="mt-1">{children}</div>
    </label>
  )
}

export function SearchInput({ value, onChange, placeholder, label = 'Search', className = '' }) {
  return (
    <FilterField label={label} className={className}>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <input type="search" value={value} onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder} className={`${FILTER_INPUT} pl-9`} />
      </div>
    </FilterField>
  )
}

/** options: [[value, label], ...]; `all` is the label of the empty choice. */
export function FilterSelect({ label, value, onChange, options, all, className = '' }) {
  return (
    <FilterField label={label} className={className}>
      <select value={value} onChange={(event) => onChange(event.target.value)} className={FILTER_INPUT}>
        {all && <option value="">{all}</option>}
        {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
      </select>
    </FilterField>
  )
}

export function ClearFilters({ visible, onClear }) {
  return visible ? <Button variant="ghost" size="sm" icon={X} onClick={onClear}>Clear filters</Button> : null
}
