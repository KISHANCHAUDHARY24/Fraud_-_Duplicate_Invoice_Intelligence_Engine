import { describe, expect, it } from 'vitest'

import { ROLE_PERMISSIONS } from '../test/renderWithAuth'
import { navigationFor, titleForPath } from './navigation'

const labelsFor = (role) => {
  const permissions = ROLE_PERMISSIONS[role]
  const can = (...required) => required.some((p) => permissions.includes(p))
  return navigationFor(can).flatMap((section) => section.items.map((item) => item.label))
}

describe('navigation', () => {
  it('shows an AP officer only what they can use', () => {
    expect(labelsFor('AP_OFFICER')).toEqual(['Dashboard', 'Invoices', 'Upload invoice', 'Fraud alerts', 'Vendors'])
  })

  it('shows a manager the approval queue but not uploads or audit logs', () => {
    const labels = labelsFor('MANAGER')
    expect(labels).toContain('Approvals')
    expect(labels).not.toContain('Upload invoice')
    expect(labels).not.toContain('Audit logs')
  })

  it('drops empty groups', () => {
    const groups = navigationFor(() => false).map((section) => section.group)
    expect(groups).toEqual(['Overview'])   // only the dashboard, available to everyone
  })

  it.each([
    ['/invoices', 'Invoices'],
    ['/invoices/upload', 'Upload invoice'],
    ['/invoices/42', 'Invoices'],
    ['/fraud-alerts/7', 'Fraud alerts'],
    ['/profile', 'My profile'],
  ])('titles %s as %s', (path, title) => {
    expect(titleForPath(path)).toBe(title)
  })
})
