import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { renderWithAuth } from '../../test/renderWithAuth'
import { isValidAccountNumber, validateVendor } from '../../utils/vendorValidation'
import VendorForm from './VendorForm'

const EMPTY = { vendor_name: 'ACME Corp', email: '', bank_name: '', account_number: '' }

describe('vendor validation', () => {
  it('matches the backend account-number rule', () => {
    expect(isValidAccountNumber('1234 5678 9012')).toBe(true)
    expect(isValidAccountNumber('GB29-NWBK-6016-1331-9268-19')).toBe(true)  // IBAN
    expect(isValidAccountNumber('12')).toBe(false)
    expect(isValidAccountNumber('1234$5678')).toBe(false)
  })

  it('needs both bank fields or neither, and a valid email', () => {
    expect(validateVendor(EMPTY, { creating: true })).toEqual({})
    expect(validateVendor({ ...EMPTY, bank_name: 'HDFC' }, { creating: true }).account_number).toMatch(/both/)
    expect(validateVendor({ ...EMPTY, email: 'not-an-email' }, { creating: true }).email).toBe('Enter a valid email address.')
    expect(validateVendor({ ...EMPTY, vendor_name: 'A' }, { creating: false }).vendor_name).toMatch(/at least 2/)
  })
})

describe('VendorForm', () => {
  it('sends the first bank account when both fields are filled', async () => {
    const onSubmit = vi.fn().mockResolvedValue({ id: 3 })
    renderWithAuth(<VendorForm onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Vendor name'), 'Globex Ltd')
    await userEvent.type(screen.getByLabelText('Bank name'), 'HDFC Bank')
    await userEvent.type(screen.getByLabelText('Account number'), '5010 1234 5678')
    await userEvent.click(screen.getByRole('button', { name: 'Create vendor' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      vendor_name: 'Globex Ltd', registration_number: null, bank_name: 'HDFC Bank', account_number: '5010 1234 5678' }))
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('status')     // only Admins change status, when editing
  })

  it('links to the existing vendor when the name is taken', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError({ status: 409, code: 'VENDOR_ALREADY_EXISTS',
      message: 'A vendor with an equivalent name already exists.', details: { existing_vendor_id: 4 } }))
    renderWithAuth(<VendorForm onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Vendor name'), 'ACME Corporation')
    await userEvent.click(screen.getByRole('button', { name: 'Create vendor' }))
    expect(await screen.findByRole('link', { name: 'Open the existing vendor' })).toHaveAttribute('href', '/vendors/4')
  })

  it('hides bank fields when editing (bank changes have their own confirmed flow)', () => {
    renderWithAuth(<VendorForm vendor={{ id: 4, vendor_name: 'ACME Corp', status: 'ACTIVE' }} onSubmit={vi.fn()} canChangeStatus />)
    expect(screen.queryByLabelText('Account number')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toHaveValue('ACTIVE')
  })
})
