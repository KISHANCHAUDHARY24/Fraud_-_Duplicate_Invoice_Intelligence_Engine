/**
 * How each system setting is shown and edited (backend/system_settings/defaults.py + validators.py).
 * The limits here only give quick feedback; the backend validator is the authority.
 */
import { SIGNAL_TYPE_OPTIONS } from './reviewOptions'

export const SETTING_GROUPS = [
  { title: 'Approval rules', description: 'When invoices are approved automatically and when they need a reviewer.',
    keys: ['approval_threshold', 'near_threshold_percent', 'auto_approve_low_risk'] },
  { title: 'Duplicate detection', description: 'How similar two invoices must be to count as a possible duplicate.',
    keys: ['duplicate_threshold', 'duplicate_weights', 'duplicate_lookback_days'] },
  { title: 'Working time', description: 'Submissions outside these hours or days raise an “unusual submission time” signal.',
    keys: ['working_hours', 'working_days', 'timezone'] },
  { title: 'Pattern rules', description: 'Windows and limits of the rule-based checks and the anomaly model.',
    keys: ['split_window_days', 'split_min_invoices', 'round_amount_base', 'bank_change_window_days', 'ml_anomaly_threshold'] },
  { title: 'Risk scoring', description: 'How signals add up to the 0–100 risk score and where each risk level starts.',
    keys: ['risk_level_thresholds', 'signal_weights', 'signal_floors'] },
]

/** editor: number | switch | text | hours | days | numberMap | floors | json */
export const SETTING_META = {
  approval_threshold: { label: 'Approval threshold', editor: 'number', unit: 'USD', min: 0.01, step: 'any' },
  near_threshold_percent: { label: '“Close to threshold” margin', editor: 'number', unit: '%', min: 0.01, max: 50, step: 'any' },
  auto_approve_low_risk: { label: 'Approve low-risk invoices automatically', editor: 'switch' },
  duplicate_threshold: { label: 'Duplicate threshold', editor: 'number', unit: '/ 100', min: 1, max: 100, step: 1 },
  duplicate_weights: { label: 'Duplicate similarity weights', editor: 'numberMap', min: 0, max: 1, step: 0.01, sumTo: 1,
    labels: { invoice_number: 'Invoice number', vendor: 'Vendor', amount: 'Amount', date: 'Invoice date', description: 'Description' } },
  duplicate_lookback_days: { label: 'Look back for duplicates', editor: 'number', unit: 'days', min: 1, max: 3650, step: 1 },
  working_hours: { label: 'Working hours', editor: 'hours' },
  working_days: { label: 'Working days', editor: 'days' },
  timezone: { label: 'Timezone', editor: 'text', placeholder: 'e.g. Asia/Kolkata, Europe/London' },
  split_window_days: { label: 'Split-purchase window', editor: 'number', unit: 'days', min: 1, max: 90, step: 1 },
  split_min_invoices: { label: 'Other invoices needed for a split', editor: 'number', unit: 'invoices', min: 1, max: 20, step: 1 },
  round_amount_base: { label: 'Round-amount base', editor: 'number', unit: 'USD', min: 1, step: 1 },
  bank_change_window_days: { label: 'Recent bank change window', editor: 'number', unit: 'days', min: 1, max: 365, step: 1 },
  ml_anomaly_threshold: { label: 'Anomaly score threshold', editor: 'number', unit: '0 – 1', min: 0, max: 1, step: 0.01 },
  risk_level_thresholds: { label: 'Risk level thresholds', editor: 'numberMap', min: 1, max: 100, step: 1,
    labels: { medium: 'Medium from', high: 'High from', critical: 'Critical from' }, increasing: ['medium', 'high', 'critical'] },
  signal_weights: { label: 'Maximum points per signal', editor: 'numberMap', min: 0, max: 100, step: 1,
    labels: Object.fromEntries(SIGNAL_TYPE_OPTIONS) },
  signal_floors: { label: 'Minimum scores for serious signals', editor: 'floors', labels: Object.fromEntries(SIGNAL_TYPE_OPTIONS) },
}

export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export const metaFor = (key) => SETTING_META[key] || { label: key.replace(/_/g, ' '), editor: 'json' }

/**
 * Number inputs hold text while typing ("0." is not a number yet). Convert a draft back to the
 * setting's real value, using the default value as the shape (number leaves become numbers).
 * An empty or invalid number becomes NaN, which `draftProblem` reports.
 */
export function fromDraft(draft, shape) {
  if (typeof shape === 'number') return draft === '' || draft === null ? Number.NaN : Number(draft)
  if (Array.isArray(shape) || shape === null || typeof shape !== 'object') return draft
  return Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, fromDraft(value, shape[key] ?? value)]))
}

function hasNaN(value) {
  if (typeof value === 'number') return Number.isNaN(value)
  if (value && typeof value === 'object') return Object.values(value).some(hasNaN)
  return false
}

/** A quick, readable problem with an edited value, or null (the server checks everything again). */
export function draftProblem(key, value) {
  const meta = metaFor(key)
  if (hasNaN(value)) return 'Enter a number in every field.'
  if (meta.sumTo !== undefined) {
    const sum = Object.values(value).reduce((total, n) => total + n, 0)
    if (Math.abs(sum - meta.sumTo) > 0.001) return `The weights must add up to ${meta.sumTo} (currently ${sum.toFixed(2)}).`
  }
  if (meta.increasing) {
    const numbers = meta.increasing.map((name) => value[name])
    if (!numbers.every((n, i) => i === 0 || n > numbers[i - 1])) return 'Each level must start higher than the one before.'
  }
  if (meta.editor === 'hours' && value.start >= value.end) return 'The start time must be before the end time.'
  if (meta.editor === 'days' && value.length === 0) return 'Choose at least one working day.'
  if (meta.editor === 'text' && !String(value).trim()) return 'This cannot be empty.'
  return null
}

/**
 * Compare values regardless of object key order: PostgreSQL JSONB re-orders keys (shortest first),
 * so {"invoice_number":…, "vendor":…} can come back as {"date":…, "amount":…}.
 */
export function sameValue(a, b) {
  const stable = (value) => (value && typeof value === 'object' && !Array.isArray(value)
    ? Object.keys(value).sort().map((key) => [key, stable(value[key])])
    : Array.isArray(value) ? value.map(stable) : value)
  return JSON.stringify(stable(a)) === JSON.stringify(stable(b))
}

/** Entries of a map setting in a readable order: the order of `labels` first, then anything else. */
export function orderedEntries(value, labels = {}) {
  const known = Object.keys(labels).filter((key) => key in value)
  const rest = Object.keys(value).filter((key) => !(key in labels))
  return [...known, ...rest].map((key) => [key, value[key]])
}

/** Short text for a value (used for "Default: …"). */
export function describeValue(key, value) {
  const meta = metaFor(key)
  if (value === null || value === undefined) return '—'
  switch (meta.editor) {
    case 'switch': return value ? 'On' : 'Off'
    case 'number': return `${value}${meta.unit ? ` ${meta.unit}` : ''}`
    case 'hours': return `${value.start}–${value.end}`
    case 'days': return value.map((day) => DAY_NAMES[day]).join(', ')
    case 'numberMap': return orderedEntries(value, meta.labels).map(([name, n]) => `${meta.labels?.[name] || name} ${n}`).join(' · ')
    case 'floors': return orderedEntries(value, meta.labels).map(([name, floor]) => `${meta.labels?.[name] || name} ≥ ${floor.min_score}`).join(' · ')
    default: return typeof value === 'object' ? JSON.stringify(value) : String(value)
  }
}
