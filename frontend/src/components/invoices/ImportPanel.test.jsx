import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import { renderWithAuth } from '../../test/renderWithAuth'
import ImportPanel from './ImportPanel'

vi.mock('../../api/invoices', () => ({ uploadCsv: vi.fn(), uploadJson: vi.fn(), submitInvoice: vi.fn(), downloadCsvTemplate: vi.fn() }))
const api = await import('../../api/invoices')

const csv = () => new File(['invoice_number,vendor\n'], 'march.csv', { type: 'text/csv' })

async function importFile(file, props = {}) {
  renderWithAuth(<ImportPanel canSubmit {...props} />)
  expect(screen.getByRole('button', { name: /import invoices/i })).toBeDisabled()   // nothing chosen yet
  await userEvent.upload(screen.getByLabelText('Choose an invoice file'), file)
  await userEvent.click(screen.getByRole('button', { name: /import invoices/i }))
}

describe('ImportPanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows partial success with a row / field / problem table', async () => {
    api.uploadCsv.mockResolvedValue({ total_rows: 3, created: 2, failed: 1, invoice_ids: [7, 8],
      errors: [{ row: 3, field: 'amount', message: 'Must be a positive number.' }] })
    await importFile(csv())
    expect(api.uploadCsv).toHaveBeenCalledWith(expect.objectContaining({ name: 'march.csv' }))
    expect(await screen.findByText('2 of 3 invoices imported')).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /3 amount Must be a positive number/ })).toBeInTheDocument()
  })

  it('submits every imported invoice for analysis and lists the outcome of each', async () => {
    api.uploadCsv.mockResolvedValue({ total_rows: 2, created: 2, failed: 0, invoice_ids: [7, 8], errors: [] })
    api.submitInvoice
      .mockResolvedValueOnce({ id: 7, invoice_number: 'INV-7', risk_level: 'LOW', risk_score: 3, approval_status: 'APPROVED' })
      .mockRejectedValueOnce(new ApiError({ status: 503, code: 'ML_SERVICE_UNAVAILABLE', message: 'ML service unavailable.' }))
    await importFile(csv())
    await userEvent.click(await screen.findByRole('button', { name: 'Submit all 2' }))
    expect(api.submitInvoice.mock.calls.map(([id]) => id)).toEqual([7, 8])          // one after another
    expect(await screen.findByRole('link', { name: 'INV-7' })).toHaveAttribute('href', '/invoices/7')
    expect(screen.getByText('ML service unavailable.')).toBeInTheDocument()          // one failure does not stop the rest
  })

  it('offers no "Submit all" to a role that cannot submit', async () => {
    api.uploadCsv.mockResolvedValue({ total_rows: 1, created: 1, failed: 0, invoice_ids: [7], errors: [] })
    await importFile(csv(), { canSubmit: false })
    await screen.findByText('1 of 1 invoices imported')
    expect(screen.queryByRole('button', { name: /submit all/i })).not.toBeInTheDocument()
  })

  it('reads JSON files and explains an invalid one without calling the server', async () => {
    await importFile(new File(['{not json'], 'bad.json', { type: 'application/json' }))
    expect(await screen.findByText(/not valid JSON/)).toBeInTheDocument()
    expect(api.uploadJson).not.toHaveBeenCalled()
  })
})
