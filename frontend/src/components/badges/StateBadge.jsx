/**
 * Status of a vendor, a fraud alert or an approval step, with icon + label (never colour alone).
 *   <StateBadge kind="alert" value="IN_REVIEW" />
 */
import {
  ArrowUpRight, Ban, CircleCheck, CircleDashed, CircleHelp, CircleX, Eye, Hourglass, PauseCircle, SearchCheck, ShieldCheck,
} from 'lucide-react'

const GREY = 'bg-slate-100 text-slate-600'
const BLUE = 'bg-blue-50 text-blue-700'
const AMBER = 'bg-amber-50 text-amber-800'
const GREEN = 'bg-green-50 text-green-700'
const RED = 'bg-red-50 text-red-700'

const STYLES = {
  vendor: {
    ACTIVE: ['Active', CircleCheck, GREEN],
    UNDER_REVIEW: ['Under review', Eye, AMBER],
    INACTIVE: ['Inactive', PauseCircle, GREY],
    BLOCKED: ['Blocked', Ban, RED],
  },
  alert: {
    OPEN: ['Open', CircleDashed, AMBER],
    IN_REVIEW: ['In review', SearchCheck, BLUE],
    RESOLVED: ['Resolved', ShieldCheck, GREEN],
    DISMISSED: ['Dismissed', CircleCheck, GREY],
  },
  decision: {
    PENDING: ['Pending', Hourglass, AMBER],
    APPROVED: ['Approved', CircleCheck, GREEN],
    REJECTED: ['Rejected', CircleX, RED],
    CLARIFICATION_REQUESTED: ['Clarification requested', CircleHelp, BLUE],
    ESCALATED: ['Escalated', ArrowUpRight, BLUE],
  },
}

export default function StateBadge({ kind, value, label }) {
  const [text, Icon, className] = STYLES[kind]?.[value] || [label || value || 'Unknown', CircleDashed, GREY]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${className}`}>
      <Icon className="size-3.5" aria-hidden />
      {label || text}
    </span>
  )
}
