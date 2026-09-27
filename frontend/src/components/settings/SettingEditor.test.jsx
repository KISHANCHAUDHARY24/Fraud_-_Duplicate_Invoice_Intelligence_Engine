import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { renderWithAuth } from '../../test/renderWithAuth'
import SettingEditor from './SettingEditor'

vi.mock('../../api/settings', () => ({ updateSetting: vi.fn(), resetSetting: vi.fn() }))
const { resetSetting, updateSetting } = await import('../../api/settings')

const WEIGHTS = { invoice_number: 0.3, vendor: 0.25, amount: 0.2, date: 0.15, description: 0.1 }
const weightsSetting = { key: 'duplicate_weights', value: WEIGHTS, default: WEIGHTS, value_type: 'JSON',
  description: 'Weights of each similarity component. Must add up to 1.0.', updated_by_name: null, updated_at: '2026-09-24T10:00:00Z' }
const thresholdSetting = { key: 'approval_threshold', value: 12000, default: 10000, value_type: 'DECIMAL',
  description: 'Invoices above this amount require manager approval.', updated_by_name: 'Priya Admin', updated_at: '2026-09-24T10:00:00Z' }

describe('SettingEditor', () => {
  beforeEach(() => vi.clearAllMocks())

  it('is read-only without the manage capability', () => {
    renderWithAuth(<SettingEditor setting={thresholdSetting} canEdit={false} onSaved={vi.fn()} />)
    expect(screen.getByLabelText('Approval threshold')).toBeDisabled()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/Default: 10000 USD · changed by Priya Admin/)).toBeInTheDocument()
  })

  it('blocks weights that do not add up to 1, then saves numbers', async () => {
    const onSaved = vi.fn()
    updateSetting.mockImplementation(async (key, value) => ({ ...weightsSetting, value }))
    renderWithAuth(<SettingEditor setting={weightsSetting} canEdit onSaved={onSaved} />)
    const vendor = screen.getByLabelText('Duplicate similarity weights: Vendor')
    await userEvent.clear(vendor)
    await userEvent.type(vendor, '0.3')
    expect(screen.getByRole('alert')).toHaveTextContent('must add up to 1 (currently 1.05)')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()

    const amount = screen.getByLabelText('Duplicate similarity weights: Amount')
    await userEvent.clear(amount)
    await userEvent.type(amount, '0.15')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(updateSetting).toHaveBeenCalledWith('duplicate_weights', { ...WEIGHTS, vendor: 0.3, amount: 0.15 })
    expect(onSaved).toHaveBeenCalled()
  })

  it('shows the backend validation message', async () => {
    updateSetting.mockRejectedValue(new ApiError({ status: 400, code: 'VALIDATION_ERROR', message: 'Invalid input.',
      details: { value: ['Must be greater than 0.'] } }))
    renderWithAuth(<SettingEditor setting={thresholdSetting} canEdit onSaved={vi.fn()} />)
    const input = screen.getByLabelText('Approval threshold')
    await userEvent.clear(input)
    await userEvent.type(input, '5')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Must be greater than 0.')
  })

  it('resets to the default after confirmation', async () => {
    resetSetting.mockResolvedValue({ ...thresholdSetting, value: 10000 })
    const onSaved = vi.fn()
    renderWithAuth(<SettingEditor setting={thresholdSetting} canEdit onSaved={onSaved} />)
    await userEvent.click(screen.getByRole('button', { name: 'Reset to default' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Reset to default' }))
    expect(resetSetting).toHaveBeenCalledWith('approval_threshold')
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ value: 10000 }), 'reset')
  })
})
