import { describe, expect, it } from 'vitest'

import { formatCurrency, formatDate, formatDateTime, initials, timeAgo } from './format'

describe('formatCurrency', () => {
  it('formats money and survives odd input', () => {
    expect(formatCurrency('9900.5')).toBe('$9,900.50')
    expect(formatCurrency(1200, 'EUR')).toBe('€1,200.00')
    expect(formatCurrency(10, 'XYZ1')).toBe('10.00 XYZ1')        // invalid currency code
    expect(formatCurrency(null)).toBe('—')
    expect(formatCurrency('')).toBe('—')
    expect(formatCurrency('abc')).toBe('abc')
  })
})

describe('dates', () => {
  it('shows day, short month and year; missing or bad values stay readable', () => {
    expect(formatDate('2026-09-24')).toBe('24 Sept 2026')
    expect(formatDate(null)).toBe('—')
    expect(formatDate('not a date')).toBe('not a date')
    expect(formatDateTime('2026-09-24T06:40:00Z')).toMatch(/24 Sept 2026, \d{2}:\d{2}/)
    expect(formatDateTime(undefined)).toBe('—')
  })

  it('timeAgo', () => {
    const now = Date.parse('2026-09-24T12:00:00Z')
    expect(timeAgo('2026-09-24T11:59:30Z', now)).toBe('just now')
    expect(timeAgo('2026-09-24T11:55:00Z', now)).toBe('5 minutes ago')
    expect(timeAgo('2026-09-24T11:00:00Z', now)).toBe('1 hour ago')
    expect(timeAgo('2026-09-21T12:00:00Z', now)).toBe('3 days ago')
    expect(timeAgo(null, now)).toBe('')
  })
})

describe('initials', () => {
  it('uses the first and last name', () => {
    expect(initials('Asha Patel')).toBe('AP')
    expect(initials('Meera Kumari Iyer')).toBe('MI')
    expect(initials('admin')).toBe('AD')
    expect(initials('')).toBe('?')
  })
})
