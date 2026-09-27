import { describe, expect, it } from 'vitest'

import { customRange, detectPreset, presetRange, rangeError } from './dateRanges'
import { describeValue, draftProblem, fromDraft, orderedEntries, sameValue } from './settingsMeta'

const TODAY = new Date(2026, 8, 24) // 24 Sept 2026 (months are 0-based)

describe('date range presets', () => {
  it('computes whole-month presets like the backend', () => {
    expect(presetRange('3m', TODAY)).toEqual({ date_from: '2026-07-01', date_to: '2026-09-24' })
    expect(presetRange('year', TODAY)).toEqual({ date_from: '2026-01-01', date_to: '2026-09-24' })
    expect(presetRange('last-year', TODAY)).toEqual({ date_from: '2025-01-01', date_to: '2025-12-31' })
    expect(presetRange('12m', TODAY)).toEqual({ date_from: '', date_to: '' })   // server default
  })

  it('recognises presets and falls back to custom', () => {
    expect(detectPreset('', '', TODAY)).toBe('12m')
    expect(detectPreset('2026-07-01', '2026-09-24', TODAY)).toBe('3m')
    expect(detectPreset('2026-02-03', '2026-09-24', TODAY)).toBe('custom')
  })

  it('"Custom" writes out the default range so it can be edited', () => {
    expect(customRange('', '', TODAY)).toEqual({ date_from: '2025-10-01', date_to: '2026-09-24' })
    expect(detectPreset('2025-10-01', '2026-09-24', TODAY)).toBe('custom')
  })

  it('rejects a reversed range', () => {
    expect(rangeError('2026-09-10', '2026-09-01')).toMatch(/on or before/)
    expect(rangeError('2026-09-01', '')).toBeNull()
  })
})

describe('settings drafts', () => {
  it('turns typed text back into numbers using the saved value as the shape', () => {
    expect(fromDraft('10000', 10000)).toBe(10000)
    expect(fromDraft({ start: '09:00', end: '18:00' }, { start: '08:00', end: '19:00' })).toEqual({ start: '09:00', end: '18:00' })
    expect(fromDraft({ DUPLICATE: { min_strength: '0.8', min_score: '60' } }, { DUPLICATE: { min_strength: 0.9, min_score: 60 } }))
      .toEqual({ DUPLICATE: { min_strength: 0.8, min_score: 60 } })
    expect(Number.isNaN(fromDraft('', 5))).toBe(true)
  })

  it('reports problems before the request is sent', () => {
    expect(draftProblem('approval_threshold', Number.NaN)).toBe('Enter a number in every field.')
    expect(draftProblem('duplicate_weights', { invoice_number: 0.3, vendor: 0.3, amount: 0.2, date: 0.15, description: 0.1 }))
      .toMatch(/add up to 1 \(currently 1.05\)/)
    expect(draftProblem('risk_level_thresholds', { medium: 30, high: 30, critical: 80 })).toMatch(/higher than the one before/)
    expect(draftProblem('working_hours', { start: '19:00', end: '08:00' })).toMatch(/before the end/)
    expect(draftProblem('working_days', [])).toMatch(/at least one/)
    expect(draftProblem('risk_level_thresholds', { medium: 30, high: 60, critical: 80 })).toBeNull()
  })

  it('ignores the key order PostgreSQL JSONB returns', () => {
    const fromDb = { date: 0.15, amount: 0.2, vendor: 0.25, description: 0.1, invoice_number: 0.3 }
    const defaults = { invoice_number: 0.3, vendor: 0.25, amount: 0.2, date: 0.15, description: 0.1 }
    expect(sameValue(fromDb, defaults)).toBe(true)
    expect(sameValue({ ...fromDb, date: 0.2 }, defaults)).toBe(false)
    expect(sameValue([0, 1], [1, 0])).toBe(false)                        // list order does matter
    expect(orderedEntries(fromDb, { invoice_number: 'Invoice number', vendor: 'Vendor' }).map(([key]) => key))
      .toEqual(['invoice_number', 'vendor', 'date', 'amount', 'description'])
  })

  it('describes values for the "Default:" line', () => {
    expect(describeValue('working_days', [0, 1, 2, 3, 4])).toBe('Mon, Tue, Wed, Thu, Fri')
    expect(describeValue('auto_approve_low_risk', true)).toBe('On')
    expect(describeValue('split_window_days', 7)).toBe('7 days')
  })
})
