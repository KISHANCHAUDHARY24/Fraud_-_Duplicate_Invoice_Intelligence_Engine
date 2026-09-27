import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import ValueChanges from '../components/audit/ValueChanges'
import { fakeAuth, renderWithAuth } from '../test/renderWithAuth'
import ReportsPage from './ReportsPage'

vi.mock('../api/reports', () => ({ reportTypes: vi.fn(), downloadReport: vi.fn() }))
const { downloadReport, reportTypes } = await import('../api/reports')

const TYPES = [
  { type: 'invoices', title: 'Invoice report', description: 'Every invoice.', date_basis: 'invoice date', formats: ['csv', 'pdf'] },
  { type: 'approvals', title: 'Approval report', description: 'Steps.', date_basis: 'date the step was opened', formats: ['csv', 'pdf'] },
]

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    reportTypes.mockResolvedValue(TYPES)
  })

  it('downloads a report for the chosen period and reports the row count', async () => {
    downloadReport.mockResolvedValue({ filename: 'expense-intelligence_invoices.csv', rows: 42, truncated: false })
    renderWithAuth(<ReportsPage />, { route: '/reports?date_from=2026-01-01&date_to=2026-06-30', auth: fakeAuth({ role: 'MANAGER' }) })
    await userEvent.click(await screen.findByRole('button', { name: 'Download Invoice report as CSV' }))
    expect(downloadReport).toHaveBeenCalledWith('invoices', { format: 'csv', date_from: '2026-01-01', date_to: '2026-06-30' })
    expect(await screen.findByText('expense-intelligence_invoices.csv downloaded (42 rows).')).toBeInTheDocument()
  })

  it('shows the reason when an export is refused', async () => {
    downloadReport.mockRejectedValue(new ApiError({ status: 403, code: 'PERMISSION_DENIED', message: 'Your role cannot export this report.' }))
    renderWithAuth(<ReportsPage />, { route: '/reports', auth: fakeAuth({ role: 'MANAGER' }) })
    await userEvent.click(await screen.findByRole('button', { name: 'Download Approval report as PDF' }))
    expect(await screen.findByText('Your role cannot export this report.')).toBeInTheDocument()
  })

  it('disables downloads while the period is impossible', async () => {
    renderWithAuth(<ReportsPage />, { route: '/reports?date_from=2026-09-10&date_to=2026-09-01', auth: fakeAuth({ role: 'MANAGER' }) })
    expect(await screen.findByRole('button', { name: 'Download Invoice report as CSV' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('on or before the end date')
  })
})

describe('ValueChanges (audit log details)', () => {
  it('lists every field with before and after', () => {
    renderWithAuth(<ValueChanges oldValue={{ status: 'UNDER_REVIEW', amount: 5 }} newValue={{ status: 'APPROVED', amount: 5 }} />)
    const statusRow = screen.getByRole('row', { name: /status/ })
    expect(statusRow).toHaveTextContent('UNDER_REVIEW')
    expect(statusRow).toHaveTextContent('APPROVED')
    expect(screen.getByRole('row', { name: /amount/ })).toHaveTextContent('5')
  })

  it('says when nothing was recorded', () => {
    renderWithAuth(<ValueChanges oldValue={null} newValue={null} />)
    expect(screen.getByText('No values were recorded for this action.')).toBeInTheDocument()
  })
})
