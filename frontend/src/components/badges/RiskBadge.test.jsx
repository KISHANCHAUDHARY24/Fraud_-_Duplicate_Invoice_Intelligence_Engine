import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import RiskBadge from './RiskBadge'
import StatusBadge from './StatusBadge'

describe('RiskBadge', () => {
  it.each([
    ['LOW', 'Low'],
    ['MEDIUM', 'Medium'],
    ['HIGH', 'High'],
    ['CRITICAL', 'Critical'],
  ])('shows text AND an icon for %s (never colour alone)', (level, label) => {
    const { container } = render(<RiskBadge level={level} />)
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeNull()
    expect(screen.getByText('risk', { exact: false })).toBeInTheDocument() // screen-reader text
  })

  it('adds the score when given', () => {
    render(<RiskBadge level="HIGH" score={72} />)
    expect(screen.getByText('High · 72')).toBeInTheDocument()
  })

  it('handles invoices that are not analysed yet', () => {
    render(<RiskBadge level={null} score={null} />)
    expect(screen.getByText('Not analysed')).toBeInTheDocument()
  })

  it('reminds users that a risk level is not a fraud finding', () => {
    const { container } = render(<RiskBadge level="CRITICAL" />)
    expect(container.firstChild).toHaveAttribute('title', expect.stringContaining('not a finding of fraud'))
  })
})

describe('StatusBadge', () => {
  it('labels every workflow status', () => {
    render(<StatusBadge status="UNDER_REVIEW" />)
    expect(screen.getByText('Under review')).toBeInTheDocument()
  })

  it('makes clear that payment is simulated', () => {
    render(<StatusBadge status="PAID" />)
    expect(screen.getByText('Paid (simulated)')).toBeInTheDocument()
  })
})
