/**
 * Chart colours and mark specs (docs/frontend.md §9).
 * The colour sets were checked with the data-viz palette validator on the white card surface:
 *   - SERIES: 4-slot categorical palette, fixed order: PASS (worst colour-blind ΔE 9.1).
 *     Aqua and yellow are below 3:1 on white, so every chart has a legend or labels AND a table view.
 *   - RISK_RAMP: one-hue ordinal ramp (darker = more severe): PASS all ordinal checks.
 *     The risk *badge* colours failed as chart colours (High vs Medium ΔE 0.6 for deuteranopia),
 *     so charts use this ramp; badges keep their colours because they always show icon + word.
 */
export const SURFACE = '#ffffff'

export const INK = {
  primary: '#0f172a',
  secondary: '#52514e',
  muted: '#898781',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
}

/** Categorical slots, always assigned in this order (never cycled, never by rank). */
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']

export const RISK_RAMP = {
  LOW: '#86b6ef',
  MEDIUM: '#3987e5',
  HIGH: '#256abf',
  CRITICAL: '#184f95',
  NOT_ANALYZED: '#c3c2b7',
}

export const BAR_SIZE = 24          // bars never thicker than 24px
export const BAR_RADIUS_TOP = [4, 4, 0, 0]
export const BAR_RADIUS_END = [0, 4, 4, 0] // horizontal bars: rounded at the data end

export const axisProps = {
  stroke: INK.axis,
  tick: { fill: INK.muted, fontSize: 12 },
  tickLine: false,
}

export const gridProps = { stroke: INK.grid, strokeDasharray: '', vertical: false }

const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
export const formatCompact = (value) => compact.format(value)
export const formatCompactMoney = (value) => `$${compact.format(value)}`

/** '2026-09' -> 'Sep 26' */
export function monthLabel(key) {
  const [year, month] = key.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })
}

/** The last `count` month keys ('2025-10' … '2026-09'), oldest first, like the backend's month_keys(). */
export function lastMonths(count = 12, today = new Date()) {
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(today.getFullYear(), today.getMonth() - (count - 1 - index), 1)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  })
}

/** Add zero rows for months without data, so gaps show as zero instead of being skipped. */
export function fillMonths(rows, keys = lastMonths()) {
  const byMonth = Object.fromEntries(rows.map((row) => [row.month, row]))
  return keys.map((month) => byMonth[month] || { month, total: 0, count: 0 })
}
