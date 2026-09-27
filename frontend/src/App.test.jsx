/**
 * Smoke test of the whole route table: every page renders for every role that may open it, and every
 * other role gets the "no access" page. The expected table mirrors backend/accounts/capabilities.py, so a
 * route guarded with the wrong capability fails here. The API is mocked with empty data.
 */
import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { fakeAuth, renderWithAuth } from './test/renderWithAuth'

// vi.mock factories are hoisted above imports, so shared test data must be hoisted too.
const { page } = vi.hoisted(() => ({ page: { count: 0, results: [] } }))
vi.mock('./api/dashboard', () => ({
  fetchDashboardSummary: vi.fn().mockResolvedValue({
    kpis: { total_invoices: 0, total_spending: 0, suspicious_invoices: 0, possible_duplicates: 0, pending_approvals: 0,
      pending_approvals_scope: 'all', blocked_invoices: 0 },
    monthly_spending: [], alerts_over_time: [], risk_distribution: [], status_distribution: [], vendor_risk: [],
    approval_trends: [], high_risk_invoices: [], generated_at: '2026-09-24T10:00:00Z',
  }),
}))
vi.mock('./api/system', () => ({ fetchHealth: vi.fn().mockResolvedValue({ status: 'ok', database: 'ok' }) }))
vi.mock('./api/notifications', () => ({ unreadCount: vi.fn().mockResolvedValue(0), latestNotifications: vi.fn().mockResolvedValue([]) }))
vi.mock('./api/invoices', () => ({ listInvoices: vi.fn().mockResolvedValue(page), cleanParams: (p) => p }))
vi.mock('./api/vendors', () => ({ listVendors: vi.fn().mockResolvedValue(page), vendorOptions: vi.fn().mockResolvedValue([]) }))
vi.mock('./api/fraud', () => ({ listAlerts: vi.fn().mockResolvedValue(page) }))
vi.mock('./api/approvals', () => ({ listApprovals: vi.fn().mockResolvedValue(page) }))
vi.mock('./api/analytics', () => ({
  fetchAnalytics: vi.fn().mockResolvedValue({
    range: { date_from: '2025-10-01', date_to: '2026-09-24' },
    summary: { invoice_count: 0, analysed_count: 0, total_spending: 0, average_invoice: 0, alert_count: 0, open_alert_count: 0,
      duplicate_rate: 0, high_risk_rate: 0, average_risk_score: 0, decisions: 0, auto_approval_rate: 0, average_decision_hours: null },
    monthly: [], risk_distribution: [], signal_frequency: [], vendor_risk: [], approval_times: [],
    department_spending: [], category_spending: [],
  }),
}))
vi.mock('./api/reports', () => ({ reportTypes: vi.fn().mockResolvedValue([]), downloadReport: vi.fn() }))
vi.mock('./api/audit', () => ({
  listAuditLogs: vi.fn().mockResolvedValue(page), auditActions: vi.fn().mockResolvedValue([]),
  auditEntityTypes: vi.fn().mockResolvedValue([]),
}))
vi.mock('./api/settings', () => ({ listSettings: vi.fn().mockResolvedValue([]) }))

const ALL = ['ADMIN', 'AP_OFFICER', 'MANAGER', 'AUDITOR']
// [route, page heading, roles that may open it]
const ROUTES = [
  ['/dashboard', /Welcome/, ALL],
  ['/invoices', 'Invoices', ALL],
  ['/invoices/upload', 'Upload invoice', ['ADMIN', 'AP_OFFICER']],
  ['/vendors', 'Vendors', ALL],
  ['/vendors/new', 'New vendor', ['ADMIN', 'AP_OFFICER']],
  ['/fraud-alerts', 'Fraud alerts', ALL],
  ['/approvals', 'Approvals', ['ADMIN', 'MANAGER', 'AUDITOR']],
  ['/analytics', 'Analytics', ['ADMIN', 'MANAGER', 'AUDITOR']],
  ['/audit-logs', 'Audit logs', ['ADMIN', 'AUDITOR']],
  ['/reports', 'Reports', ['ADMIN', 'MANAGER', 'AUDITOR']],
  ['/settings', 'Settings', ['ADMIN', 'MANAGER', 'AUDITOR']],
  ['/profile', 'My profile', ALL],
]
// Pages are lazy-loaded: the first import of a page (e.g. the chart library) is compiled on demand in tests.
const WAIT = { timeout: 8000 }
const CASES = ROUTES.flatMap(([route, heading, allowed]) => ALL.map((role) => [route, role, heading, allowed.includes(role)]))

describe('route table', () => {
  it.each(CASES)('%s as %s', async (route, role, heading, allowed) => {
    renderWithAuth(<App />, { route, auth: fakeAuth({ role }) })
    if (allowed) {
      expect(await screen.findByRole('heading', { level: 1, name: heading }, WAIT)).toBeInTheDocument()
    } else {
      expect(await screen.findByText('You do not have access to this page', {}, WAIT)).toBeInTheDocument()
    }
  })

  it('shows "not found" for an unknown address and sends / to the dashboard', async () => {
    renderWithAuth(<App />, { route: '/no-such-page', auth: fakeAuth({ role: 'MANAGER' }) })
    expect(await screen.findByText(/not found/i, {}, WAIT)).toBeInTheDocument()
  })
})
