import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fakeAuth, renderWithAuth } from '../test/renderWithAuth'
import InvoiceListPage from './InvoiceListPage'

vi.mock('../api/invoices', () => ({ listInvoices: vi.fn() }))
vi.mock('../api/vendors', () => ({ vendorOptions: vi.fn().mockResolvedValue([{ id: 4, vendor_name: 'ACME Corp' }]) }))
const { listInvoices } = await import('../api/invoices')

const INVOICE = { id: 1, invoice_number: 'INV-1001', vendor_name: 'ACME Corp', amount: '9900.00', currency: 'USD',
  invoice_date: '2026-09-01', risk_level: 'HIGH', risk_score: 72, approval_status: 'UNDER_REVIEW', department: 'IT' }

function ShowLocation() {
  const location = useLocation()
  return <p data-testid="location">{location.search}</p>
}

function renderList(route = '/invoices', role = 'AP_OFFICER') {
  return renderWithAuth(
    <Routes><Route path="/invoices" element={<><InvoiceListPage /><ShowLocation /></>} /></Routes>,
    { route, auth: fakeAuth({ role }) },
  )
}

describe('InvoiceListPage', () => {
  beforeEach(() => listInvoices.mockReset().mockResolvedValue({ count: 1, results: [INVOICE] }))

  it('reads filters from the URL and sends them to the API', async () => {
    renderList('/invoices?risk_level=HIGH,CRITICAL&ordering=-risk_score&page=2')
    expect(await screen.findByRole('link', { name: 'INV-1001' })).toHaveAttribute('href', '/invoices/1')
    expect(listInvoices).toHaveBeenLastCalledWith(expect.objectContaining({
      risk_level: 'HIGH,CRITICAL', ordering: '-risk_score', page: '2', page_size: 20 }))
    expect(screen.getByText('High · 72')).toBeInTheDocument()
  })

  it('writes filter changes to the URL and returns to page 1', async () => {
    renderList('/invoices?page=3')
    await screen.findByRole('link', { name: 'INV-1001' })
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'BLOCKED')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?approval_status=BLOCKED'))
    expect(screen.getByTestId('location')).not.toHaveTextContent('page=')
  })

  it('sorts by clicking a column header', async () => {
    renderList()
    await screen.findByRole('link', { name: 'INV-1001' })
    await userEvent.click(screen.getByRole('button', { name: /amount/i }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('ordering=amount'))
  })

  it('shows an empty state when nothing matches', async () => {
    listInvoices.mockResolvedValue({ count: 0, results: [] })
    renderList('/invoices?search=nothing')
    expect(await screen.findByText('No invoices match')).toBeInTheDocument()
  })

  it('offers "Upload invoice" only to roles that can create invoices', async () => {
    renderList('/invoices', 'MANAGER')
    await screen.findByRole('link', { name: 'INV-1001' })
    expect(screen.queryByRole('link', { name: /upload invoice/i })).not.toBeInTheDocument()
  })
})
