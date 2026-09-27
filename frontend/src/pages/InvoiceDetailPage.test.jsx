import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import { fakeAuth, renderWithAuth } from '../test/renderWithAuth'
import InvoiceDetailPage from './InvoiceDetailPage'

vi.mock('../api/invoices', () => ({
  getInvoice: vi.fn(), similarInvoices: vi.fn(), invoiceHistory: vi.fn(), submitInvoice: vi.fn(),
  reanalyzeInvoice: vi.fn(), deleteInvoice: vi.fn(),
}))
vi.mock('../api/approvals', () => ({ listApprovals: vi.fn(), simulatePayment: vi.fn(), decideApproval: vi.fn() }))
vi.mock('../api/fraud', () => ({ listAlerts: vi.fn() }))
const invoices = await import('../api/invoices')
const approvals = await import('../api/approvals')
const fraud = await import('../api/fraud')

const ANALYSIS = { risk_score: 64, risk_level: 'HIGH', summary: 'Risk score 64/100 (HIGH).', explanation: ['98% similarity (+30)'],
  warnings: [], signals: [], model_version: 'iforest-test', analyzed_at: '2026-09-24T10:00:00Z',
  disclaimer: 'Risk indicators require human review. This score is not a determination of fraud.' }
const BASE = { id: 12, invoice_number: 'INV1001', vendor_name: 'Cobalt Software Ltd', amount: '5000.00', currency: 'USD', tax: '0.00',
  submitted_by: 1, submitted_by_name: 'Asha Patel', invoice_date: '2026-09-22', department: 'IT', purchase_category: 'SOFTWARE',
  description: 'Software licence', items: [], fraud_status: 'FLAGGED', fraud_status_label: 'Flagged for review' }
const DRAFT = { ...BASE, approval_status: 'DRAFT', is_editable: true, risk_level: null, risk_score: null, latest_analysis: null,
  fraud_status: 'NOT_ANALYZED', fraud_status_label: 'Not analysed' }
const UNDER_REVIEW = { ...BASE, approval_status: 'UNDER_REVIEW', is_editable: false, risk_level: 'HIGH', risk_score: 64, latest_analysis: ANALYSIS }
const APPROVED = { ...UNDER_REVIEW, approval_status: 'APPROVED' }

function show(invoice, role, { pending = [], alerts = [] } = {}) {
  invoices.getInvoice.mockResolvedValue(invoice)
  approvals.listApprovals.mockResolvedValue({ count: pending.length, results: pending })
  fraud.listAlerts.mockResolvedValue({ count: alerts.length, results: alerts })
  // fakeAuth's user has id 1 (= the AP officer who submitted BASE); reviewers get another id.
  const user = role === 'AP_OFFICER' ? undefined : { id: 5 }
  return renderWithAuth(<Routes><Route path="/invoices/:id" element={<InvoiceDetailPage />} /></Routes>,
    { route: '/invoices/12', auth: fakeAuth({ role, user }) })
}

const button = (name) => screen.queryByRole('button', { name })

describe('InvoiceDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    invoices.similarInvoices.mockResolvedValue([])
    invoices.invoiceHistory.mockResolvedValue([])
  })

  it('a draft can be edited, deleted and submitted by its AP officer', async () => {
    invoices.submitInvoice.mockResolvedValue({ ...UNDER_REVIEW })
    show(DRAFT, 'AP_OFFICER')
    expect(await screen.findByRole('heading', { name: 'INV1001' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute('href', '/invoices/12/edit')
    expect(button('Delete')).toBeInTheDocument()
    expect(button('Re-analyse')).not.toBeInTheDocument()
    expect(screen.getByText(/has not been analysed yet/)).toBeInTheDocument()
    await userEvent.click(button('Submit for analysis'))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Submit' }))
    expect(invoices.submitInvoice).toHaveBeenCalledWith('12')
    expect(await screen.findByText(/Sent for review/)).toBeInTheDocument()
  })

  it('after submission the AP officer can only read it', async () => {
    show(UNDER_REVIEW, 'AP_OFFICER')
    await screen.findByRole('heading', { name: 'INV1001' })
    for (const name of ['Delete', 'Submit for analysis', 'Simulate payment', 'Approve']) expect(button(name)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.getByText('Risk indicators require human review. This score is not a determination of fraud.')).toBeInTheDocument()
  })

  it('the assigned manager gets the decision panel and a link to the investigation', async () => {
    const approval = { id: 3, invoice: 12, invoice_number: 'INV1001', amount: '5000.00', currency: 'USD', decision: 'PENDING',
      assigned_to: 5, level: 'MANAGER', level_label: 'Manager review' }
    show(UNDER_REVIEW, 'MANAGER', { pending: [approval], alerts: [{ id: 8, status: 'OPEN' }] })
    expect(await screen.findByText('Your decision is needed')).toBeInTheDocument()
    expect(approvals.listApprovals).toHaveBeenCalledWith({ invoice: '12', decision: 'PENDING' })
    for (const name of ['Approve', 'Reject', 'Clarify', 'Escalate']) expect(button(name)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Investigation/ })).toHaveAttribute('href', '/fraud-alerts/8')
  })

  it('an Admin can simulate the payment of an approved invoice', async () => {
    approvals.simulatePayment.mockResolvedValue({ reference: 'SIM-PAY-ABC123' })
    show(APPROVED, 'ADMIN')
    await userEvent.click(await screen.findByRole('button', { name: 'Simulate payment' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('no money is transferred')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Mark as paid' }))
    expect(approvals.simulatePayment).toHaveBeenCalledWith('12')
    expect(await screen.findByText(/SIM-PAY-ABC123/)).toBeInTheDocument()
  })

  it('explains when the analysis could not run', async () => {
    show({ ...UNDER_REVIEW, fraud_status: 'ANALYSIS_FAILED', latest_analysis: null }, 'AUDITOR')
    expect(await screen.findByText('The fraud analysis could not run')).toBeInTheDocument()
    expect(button('Re-analyse')).toBeInTheDocument()
  })

  it('an invoice outside your scope is "not found"', async () => {
    invoices.getInvoice.mockRejectedValue(new ApiError({ status: 404, code: 'NOT_FOUND', message: 'Not found.' }))
    approvals.listApprovals.mockResolvedValue({ count: 0, results: [] })
    fraud.listAlerts.mockResolvedValue({ count: 0, results: [] })
    renderWithAuth(<Routes><Route path="/invoices/:id" element={<InvoiceDetailPage />} /></Routes>,
      { route: '/invoices/99', auth: fakeAuth({ role: 'AP_OFFICER' }) })
    expect(await screen.findByText('Invoice not found')).toBeInTheDocument()
  })
})
