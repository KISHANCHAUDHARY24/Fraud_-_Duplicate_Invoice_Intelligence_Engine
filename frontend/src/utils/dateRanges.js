/**
 * Date-range presets for analytics and reports. Dates are local YYYY-MM-DD strings (no time zone shifts).
 * "Last 12 months" = the 12 whole calendar months up to today, the same default as the backend.
 */
const pad = (n) => String(n).padStart(2, '0')
export const isoDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

function monthsBack(today, months) {
  return isoDate(new Date(today.getFullYear(), today.getMonth() - (months - 1), 1))
}

export const RANGE_PRESETS = [
  ['12m', 'Last 12 months'],
  ['3m', 'Last 3 months'],
  ['month', 'This month'],
  ['year', 'This year'],
  ['last-year', 'Last year'],
  ['custom', 'Custom range'],
]

/** { date_from, date_to } for a preset. '12m' returns empty values: the server default. */
export function presetRange(preset, today = new Date()) {
  const to = isoDate(today)
  switch (preset) {
    case '3m': return { date_from: monthsBack(today, 3), date_to: to }
    case 'month': return { date_from: monthsBack(today, 1), date_to: to }
    case 'year': return { date_from: `${today.getFullYear()}-01-01`, date_to: to }
    case 'last-year': return { date_from: `${today.getFullYear() - 1}-01-01`, date_to: `${today.getFullYear() - 1}-12-31` }
    default: return { date_from: '', date_to: '' }
  }
}

/** "Custom range" starts from the dates in effect, written out (the default range has empty values). */
export function customRange(dateFrom, dateTo, today = new Date()) {
  return dateFrom || dateTo ? { date_from: dateFrom, date_to: dateTo }
    : { date_from: monthsBack(today, 12), date_to: isoDate(today) }
}

/** Which preset the current values correspond to (for the drop-down). */
export function detectPreset(dateFrom, dateTo, today = new Date()) {
  if (!dateFrom && !dateTo) return '12m'
  const match = RANGE_PRESETS.find(([key]) => {
    if (key === 'custom' || key === '12m') return false
    const range = presetRange(key, today)
    return range.date_from === dateFrom && range.date_to === dateTo
  })
  return match ? match[0] : 'custom'
}

/** A readable problem with the chosen dates, or null. */
export function rangeError(dateFrom, dateTo) {
  if (dateFrom && dateTo && dateFrom > dateTo) return 'The start date must be on or before the end date.'
  return null
}
