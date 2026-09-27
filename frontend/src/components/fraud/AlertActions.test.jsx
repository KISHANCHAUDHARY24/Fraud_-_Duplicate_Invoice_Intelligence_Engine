import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fakeAuth, renderWithAuth } from '../../test/renderWithAuth'
import AlertActions from './AlertActions'

vi.mock('../../api/fraud', () => ({
  assignAlert: vi.fn(), markAlertReviewed: vi.fn(), resolveAlert: vi.fn(),
  auditorOptions: vi.fn().mockResolvedValue([{ id: 1, name: 'Asha Patel' }, { id: 9, name: 'Meera Iyer' }]),
}))
const { assignAlert, resolveAlert } = await import('../../api/fraud')

const ALERT = { id: 5, status: 'OPEN', assigned_to: null }
const INVOICE = { id: 12, submitted_by: 44 }
const asRole = (role) => ({ auth: fakeAuth({ role }) })

describe('AlertActions', () => {
  beforeEach(() => vi.clearAllMocks())

  it('gives an auditor assign, review and resolve on an open alert', () => {
    renderWithAuth(<AlertActions alert={ALERT} invoice={INVOICE} onChanged={vi.fn()} />, asRole('AUDITOR'))
    for (const name of ['Assign', 'Start review', 'Resolve']) expect(screen.getByRole('button', { name })).toBeInTheDocument()
  })

  it('shows nothing to a manager, and nothing on a closed alert', () => {
    const { unmount } = renderWithAuth(<AlertActions alert={ALERT} invoice={INVOICE} onChanged={vi.fn()} />, asRole('MANAGER'))
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    unmount()
    renderWithAuth(<AlertActions alert={{ ...ALERT, status: 'RESOLVED' }} invoice={INVOICE} onChanged={vi.fn()} />, asRole('AUDITOR'))
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('never offers "Resolve" on an invoice the auditor submitted', () => {
    renderWithAuth(<AlertActions alert={ALERT} invoice={{ ...INVOICE, submitted_by: 1 }} onChanged={vi.fn()} />, asRole('AUDITOR'))
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument()
  })

  it('resolving needs an outcome AND a note', async () => {
    const onChanged = vi.fn()
    resolveAlert.mockResolvedValue({ id: 5, status: 'RESOLVED' })
    renderWithAuth(<AlertActions alert={ALERT} invoice={INVOICE} onChanged={onChanged} />, asRole('AUDITOR'))
    await userEvent.click(screen.getByRole('button', { name: 'Resolve' }))
    const confirm = screen.getByRole('button', { name: 'Resolve alert' })
    expect(confirm).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/Issue confirmed/))
    expect(confirm).toBeDisabled()                                  // still no note
    await userEvent.type(screen.getByLabelText(/Investigation note/), 'Vendor denies sending this invoice')
    await userEvent.click(confirm)
    expect(resolveAlert).toHaveBeenCalledWith(5, 'CONFIRMED_ISSUE', 'Vendor denies sending this invoice')
    expect(onChanged).toHaveBeenCalledWith({ id: 5, status: 'RESOLVED' })
  })

  it('assigns to the chosen auditor', async () => {
    assignAlert.mockResolvedValue({ id: 5, status: 'OPEN', assigned_to: 9 })
    renderWithAuth(<AlertActions alert={ALERT} invoice={INVOICE} onChanged={vi.fn()} />, asRole('ADMIN'))
    expect(screen.queryByRole('button', { name: 'Resolve' })).not.toBeInTheDocument() // Admins assign, auditors resolve
    await userEvent.click(screen.getByRole('button', { name: 'Assign' }))
    await userEvent.selectOptions(await screen.findByLabelText('Auditor'), await screen.findByRole('option', { name: 'Meera Iyer' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Assign' }))
    expect(assignAlert).toHaveBeenCalledWith(5, 9)
  })
})
