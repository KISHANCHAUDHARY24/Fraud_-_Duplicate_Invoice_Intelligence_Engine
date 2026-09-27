/**
 * Capability names, identical to backend/accounts/capabilities.py.
 * The backend sends the logged-in user's list in GET /api/auth/me/ ("permissions").
 * The frontend uses them ONLY to show or hide UI; the backend enforces them.
 */
export const Cap = Object.freeze({
  USERS_MANAGE: 'users.manage',
  SETTINGS_VIEW: 'settings.view',
  SETTINGS_MANAGE: 'settings.manage',
  VENDORS_VIEW: 'vendors.view',
  VENDORS_CREATE: 'vendors.create',
  VENDORS_EDIT: 'vendors.edit',
  BANK_ACCOUNTS_VIEW: 'bank_accounts.view',
  BANK_ACCOUNTS_MANAGE: 'bank_accounts.manage',
  INVOICES_VIEW: 'invoices.view',
  INVOICES_CREATE: 'invoices.create',
  INVOICES_SUBMIT: 'invoices.submit',
  INVOICES_REANALYZE: 'invoices.reanalyze',
  FRAUD_VIEW: 'fraud.view',
  ALERTS_VIEW: 'alerts.view',
  ALERTS_ASSIGN: 'alerts.assign',
  ALERTS_RESOLVE: 'alerts.resolve',
  APPROVALS_VIEW: 'approvals.view',
  APPROVALS_DECIDE: 'approvals.decide',
  APPROVALS_ESCALATE: 'approvals.escalate',
  PAYMENTS_VIEW: 'payments.view',
  PAYMENTS_SIMULATE: 'payments.simulate',
  AUDIT_VIEW: 'audit.view',
  ANALYTICS_VIEW: 'analytics.view',
  REPORTS_EXPORT: 'reports.export',
})

export const ROLE_LABELS = Object.freeze({
  ADMIN: 'Administrator',
  AP_OFFICER: 'Accounts Payable Officer',
  MANAGER: 'Manager',
  AUDITOR: 'Auditor',
})
