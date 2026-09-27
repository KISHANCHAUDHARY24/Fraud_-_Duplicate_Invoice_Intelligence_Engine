/**
 * Period picker: a preset drop-down plus From / To dates. Values are YYYY-MM-DD strings.
 * Empty values mean the page's default, named by `defaultLabel` ("Last 12 months" for analytics, "All time" for the audit log).
 */
import { RANGE_PRESETS, customRange, detectPreset, presetRange, rangeError } from '../../utils/dateRanges'
import { FILTER_INPUT, FilterField } from './Filters'

export default function DateRangeFilter({ dateFrom, dateTo, onChange, defaultLabel = 'Last 12 months', className = '' }) {
  const preset = detectPreset(dateFrom, dateTo)
  const error = rangeError(dateFrom, dateTo)
  return (
    <div className={`grid gap-3 sm:grid-cols-3 ${className}`}>
      <FilterField label="Period">
        <select value={preset} className={FILTER_INPUT}
          onChange={(event) => onChange(event.target.value === 'custom' ? customRange(dateFrom, dateTo) : presetRange(event.target.value))}>
          {RANGE_PRESETS.map(([key, label]) => <option key={key} value={key}>{key === '12m' ? defaultLabel : label}</option>)}
        </select>
      </FilterField>
      <FilterField label="From">
        <input type="date" value={dateFrom} max={dateTo || undefined} className={FILTER_INPUT}
          aria-invalid={Boolean(error)} onChange={(event) => onChange({ date_from: event.target.value, date_to: dateTo })} />
      </FilterField>
      <FilterField label="To">
        <input type="date" value={dateTo} min={dateFrom || undefined} className={FILTER_INPUT}
          aria-invalid={Boolean(error)} onChange={(event) => onChange({ date_from: dateFrom, date_to: event.target.value })} />
      </FilterField>
      {error && <p role="alert" className="text-xs text-red-600 sm:col-span-3">{error}</p>}
    </div>
  )
}
