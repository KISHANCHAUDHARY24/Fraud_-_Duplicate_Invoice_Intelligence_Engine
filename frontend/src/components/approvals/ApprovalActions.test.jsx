import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fakeAuth, renderWithAuth } from '../../test/renderWithAuth'
import ApprovalActions from './ApprovalActions'

vi.mock('../../api/approvals', () => ({ decideApproval: vi.fn() }))
const { decideApproval } = await import('../../api/approvals')

// fakeAuth's user has id 1
const PENDING = { id: 7, invoice_number: 'INV-9', amount: '9800.00', currency: 'USD', decision: 'PENDING',
  assigned_to: 1, level: 'MANAGER' }
const asRole = (role) => ({ auth: fakeAuth({ role }) })

describe('ApprovalActions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('gives the assigned manager all four decisions', () => {
    renderWithAuth(<ApprovalActions approval={PENDING} onDone={vi.fn()} />, asRole('MANAGER'))
    for (const name of ['Approve', 'Reject', 'Clarify', 'Escalate']) expect(screen.getByRole('button', { name })).toBeInTheDocument()
  })

  it('shows nothing to someone else, on a decided step, or to an Admin', () => {
    const cases = [
      [{ ...PENDING, assigned_to: 2 }, 'MANAGER'],
      [{ ...PENDING, decision: 'APPROVED' }, 'MANAGER'],
      [PENDING, 'ADMIN'],
    ]
    for (const [approval, role] of cases) {
      const { unmount } = renderWithAuth(<ApprovalActions approval={approval} onDone={vi.fn()} />, asRole(role))
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
      unmount()
    }
  })

  it('does not offer "Escalate" at auditor level', () => {
    renderWithAuth(<ApprovalActions approval={{ ...PENDING, level: 'AUDITOR' }} onDone={vi.fn()} />, asRole('AUDITOR'))
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Escalate' })).not.toBeInTheDocument()
  })

  it('rejecting requires a reason, which is sent to the API', async () => {
    const onDone = vi.fn()
    decideApproval.mockResolvedValue({ ...PENDING, decision: 'REJECTED' })
    renderWithAuth(<ApprovalActions approval={PENDING} onDone={onDone} />, asRole('MANAGER'))
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    const dialog = screen.getByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Reject' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText(/Reason for rejecting/), 'No purchase order')
    await userEvent.click(confirm)
    expect(decideApproval).toHaveBeenCalledWith(7, 'reject', 'No purchase order')
    expect(onDone).toHaveBeenCalledWith({ ...PENDING, decision: 'REJECTED' }, 'reject')
  })

  it('approving works without a comment', async () => {
    decideApproval.mockResolvedValue({ ...PENDING, decision: 'APPROVED' })
    renderWithAuth(<ApprovalActions approval={PENDING} onDone={vi.fn()} />, asRole('MANAGER'))
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve' }))
    expect(decideApproval).toHaveBeenCalledWith(7, 'approve', '')
  })
})
