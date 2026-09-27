import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { renderWithAuth } from '../../test/renderWithAuth'
import { validateInvoice } from '../../utils/invoiceValidation'
import InvoiceForm from './InvoiceForm'

const VENDORS = [
  { id: 4, vendor_name: 'ACME Corp', status: 'ACTIVE' },
  { id: 5, vendor_name: 'Blocked Ltd', status: 'BLOCKED' },
]
const VALID = {
  vendor: '4', invoice_number: 'INV-1', invoice_date: '2026-09-01', due_date: '', amount: '100', currency: 'USD',
  tax: '0', purchase_category: 'OTHER', purchase_order_number: '', department: '', description: 'Paper',
}

describe('validateInvoice', () => {
  it('accepts a valid invoice', () => {
    expect(validateInvoice(VALID, '2026-09-24')).toEqual({})
  })

  it.each([
    [{ amount: '0' }, 'amount', 'Invoice amount must be greater than zero.'],
    [{ invoice_date: '2026-10-01' }, 'invoice_date', 'Invoice date cannot be in the future.'],
    [{ due_date: '2026-08-01' }, 'due_date', 'Due date cannot be before the invoice date.'],
    [{ currency: 'DOLLARS' }, 'currency', 'Use a 3-letter code, e.g. USD.'],
    [{ description: 'x' }, 'description', 'Description must be at least 3 characters.'],
    [{ vendor: '' }, 'vendor', 'Choose the vendor.'],
  ])('rejects %o', (change, field, message) => {
    expect(validateInvoice({ ...VALID, ...change }, '2026-09-24')[field]).toBe(message)
  })
})

describe('InvoiceForm', () => {
  it('only offers vendors that can receive invoices', () => {
    renderWithAuth(<InvoiceForm vendors={VENDORS} onSubmit={vi.fn()} />)
    expect(screen.getByRole('option', { name: 'ACME Corp' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Blocked Ltd' })).not.toBeInTheDocument()
  })

  it('does not call the server while fields are invalid', async () => {
    const onSubmit = vi.fn()
    renderWithAuth(<InvoiceForm vendors={VENDORS} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: /save as draft/i }))
    expect(screen.getByText('Choose the vendor.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows server field errors and links to an existing duplicate', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError({
      status: 409, code: 'DUPLICATE_INVOICE_NUMBER', message: "Invoice number 'INV-1' already exists for vendor 'ACME Corp'.",
      details: { invoice_number: 'INV-1', existing_invoice_id: 12 },
    }))
    renderWithAuth(<InvoiceForm vendors={VENDORS} onSubmit={onSubmit} submitCapable />)
    await userEvent.selectOptions(screen.getByLabelText('Vendor'), '4')
    await userEvent.type(screen.getByLabelText('Invoice number'), 'INV-1')
    await userEvent.type(screen.getByLabelText('Invoice date'), '2026-09-01')
    await userEvent.type(screen.getByLabelText('Amount'), '100')
    await userEvent.type(screen.getByLabelText('Description'), 'Paper supplies')
    await userEvent.click(screen.getByRole('button', { name: /save and submit/i }))

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ vendor: 4, invoice_number: 'INV-1', due_date: null }),
      { andSubmit: true })
    expect(await screen.findByText(/already exists for vendor/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the existing invoice' })).toHaveAttribute('href', '/invoices/12')
  })
})
