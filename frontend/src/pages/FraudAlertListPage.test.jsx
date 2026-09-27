import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fakeAuth, renderWithAuth } from '../test/renderWithAuth'
import FraudAlertListPage from './FraudAlertListPage'

vi.mock('../api/fraud', () => ({ listAlerts: vi.fn() }))
vi.mock('../api/vendors', () => ({ vendorOptions: vi.fn().mockResolvedValue([]) }))
const { listAlerts } = await import('../api/fraud')

const ALERT = { id: 5, invoice: 12, invoice_number: 'INV1001', vendor_name: 'ACME Corp', amount: '5000.00', risk_score: 64,
  severity: 'HIGH', primary_type: 'DUPLICATE', primary_type_label: 'Possible duplicate',
  signal_types: ['DUPLICATE', 'AMOUNT_ANOMALY', 'ROUND_AMOUNT'], status: 'OPEN', assigned_to_name: null,
  created_at: '2026-09-24T10:00:00Z' }

function ShowLocation() {
  return <p data-testid="location">{useLocation().search}</p>
}

const renderList = (route = '/fraud-alerts', role = 'AUDITOR') => renderWithAuth(
  <Routes><Route path="/fraud-alerts" element={<><FraudAlertListPage /><ShowLocation /></>} /></Routes>,
  { route, auth: fakeAuth({ role }) })

describe('FraudAlertListPage', () => {
  beforeEach(() => listAlerts.mockReset().mockResolvedValue({ count: 1, results: [ALERT] }))

  it('opens on open alerts and links to the investigation', async () => {
    renderList()
    expect(await screen.findByRole('link', { name: 'Alert #5' })).toHaveAttribute('href', '/fraud-alerts/5')
    expect(listAlerts).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'OPEN,IN_REVIEW', ordering: '-created_at' }))
    expect(screen.getByText('+2 more')).toBeInTheDocument()
  })

  it('keeps "All statuses" in the URL instead of falling back to the default', async () => {
    renderList()
    await screen.findByRole('link', { name: 'Alert #5' })
    await userEvent.selectOptions(screen.getByLabelText('Status'), '')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?status='))
    await waitFor(() => expect(listAlerts).toHaveBeenLastCalledWith(expect.objectContaining({ status: '' })))
  })

  it('offers "Assigned to" only to investigators', async () => {
    renderList('/fraud-alerts', 'AP_OFFICER')
    await screen.findByRole('link', { name: 'Alert #5' })
    expect(screen.queryByLabelText('Assigned to')).not.toBeInTheDocument()
  })
})
