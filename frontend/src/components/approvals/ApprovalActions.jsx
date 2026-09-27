/**
 * Decide on a pending approval step: approve, reject, ask for clarification or escalate to an auditor.
 * Used in the approval queue and on the invoice page. Only the assigned reviewer sees the buttons.
 */
import { ArrowUpRight, CircleCheck, CircleHelp, CircleX } from 'lucide-react'
import { useState } from 'react'

import { decideApproval } from '../../api/approvals'
import { useAuth } from '../../hooks/useAuth'
import { canDecide } from '../../utils/approvals'
import { formatCurrency } from '../../utils/format'
import { Cap } from '../../utils/permissions'
import Button from '../common/Button'
import ConfirmDialog from '../common/ConfirmDialog'

const ACTIONS = {
  approve: {
    title: 'Approve this invoice?', confirmLabel: 'Approve', tone: 'primary', commentRequired: false,
    commentLabel: 'Comment (optional)',
    message: (approval) => `${approval.invoice_number} (${formatCurrency(approval.amount, approval.currency)}) is approved and its payment scheduled.`,
  },
  reject: {
    title: 'Reject this invoice?', confirmLabel: 'Reject', tone: 'danger', commentRequired: true,
    commentLabel: 'Reason for rejecting',
    message: () => 'The submitter is notified with your reason. A rejected invoice cannot be paid.',
  },
  'request-clarification': {
    title: 'Ask for clarification?', confirmLabel: 'Send back', tone: 'primary', commentRequired: true,
    commentLabel: 'What needs to be clarified?',
    message: () => 'The invoice goes back to the submitter as a draft, to correct and submit again.',
  },
  escalate: {
    title: 'Escalate to an auditor?', confirmLabel: 'Escalate', tone: 'primary', commentRequired: true,
    commentLabel: 'Why does an auditor need to look at it?',
    message: () => 'An auditor becomes the reviewer. You no longer decide on this invoice.',
  },
}

const BUTTONS = [
  ['approve', 'Approve', CircleCheck, 'primary'],
  ['reject', 'Reject', CircleX, 'danger'],
  ['request-clarification', 'Clarify', CircleHelp, 'secondary'],
  ['escalate', 'Escalate', ArrowUpRight, 'secondary'],
]

/** `compact` shows icon-only buttons (named for screen readers and in a tooltip) for use inside table rows. */
export default function ApprovalActions({ approval, onDone, compact = false }) {
  const { user, can } = useAuth()
  const [action, setAction] = useState(null)
  if (!canDecide(approval, user, can)) return null
  const canEscalate = can(Cap.APPROVALS_ESCALATE) && approval.level !== 'AUDITOR'
  const current = action && ACTIONS[action]

  return (
    <div className={compact ? 'flex gap-1.5' : 'flex flex-wrap gap-2'}>
      {BUTTONS.filter(([key]) => key !== 'escalate' || canEscalate).map(([key, label, Icon, variant]) => (
        <Button key={key} size={compact ? 'icon' : 'md'} variant={variant} icon={Icon} onClick={() => setAction(key)}
          aria-label={compact ? `${label} ${approval.invoice_number}` : undefined} title={compact ? label : undefined}>
          {!compact && label}
        </Button>
      ))}
      {current && (
        <ConfirmDialog open onClose={() => setAction(null)} title={current.title} confirmLabel={current.confirmLabel}
          tone={current.tone} message={current.message(approval)} commentLabel={current.commentLabel}
          commentRequired={current.commentRequired}
          onConfirm={async (comment) => onDone(await decideApproval(approval.id, action, comment), action)} />
      )}
    </div>
  )
}
