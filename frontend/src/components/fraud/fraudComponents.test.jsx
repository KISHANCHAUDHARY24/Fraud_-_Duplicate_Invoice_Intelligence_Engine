import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderWithAuth } from '../../test/renderWithAuth'
import DuplicateComparison from './DuplicateComparison'
import RiskExplanation from './RiskExplanation'
import RiskScoreGauge from './RiskScoreGauge'

describe('RiskExplanation', () => {
  const analysis = {
    summary: 'Risk score 60/100 (HIGH). This is a risk indicator for human review, not a determination of fraud.',
    explanation: ['98% similarity with invoice INV-1001 (+29)', 'Minimum score 60 (HIGH) because a very strong duplicate match must always be reviewed'],
    warnings: ['ML model not loaded: the anomaly signal was skipped.'],
    model_version: 'iforest-test', analyzed_at: '2026-09-24T10:00:00Z',
    disclaimer: 'Risk indicators require human review. This score is not a determination of fraud.',
  }

  it('lists each reason with its points, plus warnings and the disclaimer', () => {
    renderWithAuth(<RiskExplanation analysis={analysis} />)
    const reasons = within(screen.getByRole('list', { name: 'Reasons for the risk score' })).getAllByRole('listitem')
    expect(reasons).toHaveLength(2)
    expect(reasons[0]).toHaveTextContent('98% similarity with invoice INV-1001')
    expect(reasons[0]).toHaveTextContent('+29')
    expect(reasons[1]).not.toHaveTextContent('+')          // the floor line has no points badge
    expect(screen.getByText(/ML model not loaded/)).toBeInTheDocument()
    // Both the summary and the disclaimer say it is not a fraud determination.
    expect(screen.getByText('Risk indicators require human review. This score is not a determination of fraud.')).toBeInTheDocument()
    expect(screen.getAllByText(/not a determination of fraud/)).toHaveLength(2)
  })

  it('says so when nothing was found', () => {
    renderWithAuth(<RiskExplanation analysis={{ ...analysis, explanation: [], warnings: [] }} />)
    expect(screen.getByText('No risk indicators were found.')).toBeInTheDocument()
  })
})

describe('RiskScoreGauge', () => {
  it('announces the score and level for screen readers', () => {
    renderWithAuth(<RiskScoreGauge score={72} level="HIGH" />)
    expect(screen.getByRole('img', { name: 'Risk score 72 out of 100, HIGH risk' })).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
  })
})

describe('DuplicateComparison', () => {
  it('shows both invoices side by side with per-field similarity', () => {
    const invoice = { invoice_number: 'INV1001', vendor_name: 'ACME Corp', amount: '5000.00', currency: 'USD',
      invoice_date: '2026-09-03', description: 'Software licence' }
    const match = {
      score: 98, description: 'Software License',
      components: { invoice_number: 1, vendor: 1, amount: 1, date: 0.933, description: 0.94 },
      invoice: { id: 12, invoice_number: 'INV-1001', vendor_name: 'ACME Corp', amount: '5000.00', currency: 'USD',
        invoice_date: '2026-09-01', approval_status: 'APPROVED' },
    }
    renderWithAuth(<DuplicateComparison invoice={invoice} match={match} />)
    expect(screen.getByRole('link', { name: 'INV-1001' })).toHaveAttribute('href', '/invoices/12')
    const row = screen.getByRole('row', { name: /Invoice date/ })
    expect(row).toHaveTextContent('93%')
    expect(screen.getAllByLabelText('Strong match')).toHaveLength(5)
  })
})
