import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { renderWithAuth } from '../../test/renderWithAuth'
import ChartCard from './ChartCard'

const table = { rows: [{ label: 'Low', count: 7 }], columns: [{ key: 'label', label: 'Risk level' }, { key: 'count', label: 'Invoices' }] }

describe('ChartCard', () => {
  it('switches between the chart and an accessible table of the same data', async () => {
    renderWithAuth(<ChartCard title="Risk distribution" table={table}><p>the chart</p></ChartCard>)
    expect(screen.getByText('the chart')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show as table' }))
    expect(screen.queryByText('the chart')).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Risk level' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '7' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show as table' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows an empty state instead of a blank chart', () => {
    renderWithAuth(<ChartCard title="Monthly spending" table={table} empty><p>the chart</p></ChartCard>)
    expect(screen.getByText('Nothing to show')).toBeInTheDocument()
    expect(screen.queryByText('the chart')).not.toBeInTheDocument()
  })
})
