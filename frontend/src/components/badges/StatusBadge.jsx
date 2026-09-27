import { Ban, Banknote, CircleCheck, CircleX, Hourglass, LoaderCircle, PenLine, Send } from 'lucide-react'

/** Invoice workflow status (docs/approval-workflow.md §1), with icon + label. */
const STATUS_STYLES = {
  DRAFT: { label: 'Draft', icon: PenLine, className: 'bg-slate-100 text-slate-600' },
  SUBMITTED: { label: 'Submitted', icon: Send, className: 'bg-blue-50 text-blue-700' },
  PROCESSING: { label: 'Processing', icon: LoaderCircle, className: 'bg-blue-50 text-blue-700' },
  UNDER_REVIEW: { label: 'Under review', icon: Hourglass, className: 'bg-amber-50 text-amber-800' },
  APPROVED: { label: 'Approved', icon: CircleCheck, className: 'bg-green-50 text-green-700' },
  REJECTED: { label: 'Rejected', icon: CircleX, className: 'bg-red-50 text-red-700' },
  BLOCKED: { label: 'Blocked', icon: Ban, className: 'bg-red-100 text-red-800' },
  PAID: { label: 'Paid (simulated)', icon: Banknote, className: 'bg-emerald-50 text-emerald-700' },
}

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { label: status || 'Unknown', icon: Hourglass, className: 'bg-slate-100 text-slate-600' }
  const Icon = style.icon
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${style.className}`}>
      <Icon className="size-3.5" aria-hidden />
      {style.label}
    </span>
  )
}
