/** Render a component inside a router and a fake auth context (no network). */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { AuthContext } from '../context/authContext'

/** Copied from backend/accounts/capabilities.py ROLE_CAPABILITIES (keep in sync). */
export const ROLE_PERMISSIONS = {
  ADMIN: ['alerts.assign', 'alerts.view', 'analytics.view', 'approvals.view', 'audit.view', 'bank_accounts.manage',
    'bank_accounts.view', 'fraud.view', 'invoices.create', 'invoices.reanalyze', 'invoices.submit', 'invoices.view',
    'payments.simulate', 'payments.view', 'reports.export', 'settings.manage', 'settings.view', 'users.manage',
    'vendors.create', 'vendors.edit', 'vendors.view'],
  AP_OFFICER: ['alerts.view', 'bank_accounts.view', 'fraud.view', 'invoices.create', 'invoices.reanalyze', 'invoices.submit',
    'invoices.view', 'vendors.create', 'vendors.view'],
  MANAGER: ['alerts.view', 'analytics.view', 'approvals.decide', 'approvals.escalate', 'approvals.view', 'fraud.view',
    'invoices.view', 'reports.export', 'settings.view', 'vendors.view'],
  AUDITOR: ['alerts.assign', 'alerts.resolve', 'alerts.view', 'analytics.view', 'approvals.decide', 'approvals.view',
    'audit.view', 'bank_accounts.view', 'fraud.view', 'invoices.reanalyze', 'invoices.view', 'payments.view',
    'reports.export', 'settings.view', 'vendors.view'],
}

export function fakeAuth({ role = 'AP_OFFICER', user, ...overrides } = {}) {
  const permissions = ROLE_PERMISSIONS[role] || []
  const currentUser = user === null ? null : {
    id: 1, username: 'asha', full_name: 'Asha Patel', first_name: 'Asha', email: 'asha@example.com',
    role, role_name: role, department: 'IT', permissions, ...user,
  }
  return {
    user: currentUser,
    status: 'ready',
    sessionMessage: '',
    login: async () => currentUser,
    logout: async () => {},
    refreshUser: async () => currentUser,
    setUser: () => {},
    can: (...required) => required.some((permission) => currentUser?.permissions.includes(permission)),
    ...overrides,
  }
}

export function renderWithAuth(ui, { auth = fakeAuth(), route = '/' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthContext.Provider value={auth}>{ui}</AuthContext.Provider>
    </MemoryRouter>,
  )
}
