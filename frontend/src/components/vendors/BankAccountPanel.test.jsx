import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { renderWithAuth } from '../../test/renderWithAuth'
import BankAccountPanel from './BankAccountPanel'

vi.mock('../../api/vendors', () => ({ addBankAccount: vi.fn() }))
const { addBankAccount } = await import('../../api/vendors')

const ACCOUNTS = [
  { id: 2, bank_name: 'ICICI Bank', masked_account: '****4821', is_active: true, valid_from: '2026-09-12', valid_to: null, added_by_name: 'Neha Verma' },
  { id: 1, bank_name: 'HDFC Bank', masked_account: '****1111', is_active: false, valid_from: '2025-01-01', valid_to: '2026-09-12', added_by_name: null },
]

async function fillAndContinue(bank, number) {
  await userEvent.click(screen.getByRole('button', { name: 'Change bank account' }))
  await userEvent.type(screen.getByLabelText('Bank name'), bank)
  await userEvent.type(screen.getByLabelText('New account number'), number)
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
}

describe('BankAccountPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows only masked accounts, marking which one is in use', () => {
    renderWithAuth(<BankAccountPanel vendorId={4} accounts={ACCOUNTS} canManage={false} onChanged={vi.fn()} />)
    expect(screen.getByText('****4821')).toBeInTheDocument()
    expect(screen.getByText('In use')).toBeInTheDocument()
    expect(screen.getByText('Closed')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()         // view only without bank_accounts.manage
  })

  it('checks the number, then asks for confirmation before changing it', async () => {
    const onChanged = vi.fn()
    addBankAccount.mockResolvedValue({ id: 3 })
    renderWithAuth(<BankAccountPanel vendorId={4} accounts={ACCOUNTS} canManage onChanged={onChanged} />)
    await fillAndContinue('Kotak Bank', '12')
    expect(screen.getByText(/6–34 letters or digits/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const number = screen.getByLabelText('New account number')
    await userEvent.clear(number)
    await userEvent.type(number, '7788 9900 1122')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('Admins and Auditors are notified')
    expect(addBankAccount).not.toHaveBeenCalled()                          // nothing happens before confirming
    await userEvent.click(within(dialog).getByRole('button', { name: 'Change account' }))
    expect(addBankAccount).toHaveBeenCalledWith(4, { bank_name: 'Kotak Bank', account_number: '7788 9900 1122' })
    expect(onChanged).toHaveBeenCalled()
  })

  it('shows a server field error under the field', async () => {
    addBankAccount.mockRejectedValue(new ApiError({ status: 400, code: 'VALIDATION_ERROR', message: 'Invalid input.',
      details: { account_number: ["This bank account is already the vendor's active account."] } }))
    renderWithAuth(<BankAccountPanel vendorId={4} accounts={ACCOUNTS} canManage onChanged={vi.fn()} />)
    await fillAndContinue('ICICI Bank', '5010 0048 21')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Change account' }))
    expect(await screen.findByText("This bank account is already the vendor's active account.")).toBeInTheDocument()
  })
})
