/** Every approval step of an invoice, oldest first: who reviewed it, at which level, and what they decided. */
import { formatDateTime } from '../../utils/format'
import StateBadge from '../badges/StateBadge'

export default function ApprovalTimeline({ approvals }) {
  if (!approvals?.length) return <p className="text-sm text-slate-500">No approval steps yet.</p>
  return (
    <ol className="space-y-3">
      {approvals.map((approval) => (
        <li key={approval.id} className="rounded-lg border border-slate-200 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-800">{approval.level_label}</p>
            <StateBadge kind="decision" value={approval.decision} />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Reviewer: {approval.assigned_to_name || 'automatic'} · received {formatDateTime(approval.created_at)}
          </p>
          {approval.decided_at && (
            <p className="text-xs text-slate-500">Decided by {approval.decided_by_name} · {formatDateTime(approval.decided_at)}</p>
          )}
          {approval.comment && <p className="mt-1 text-sm text-slate-700">“{approval.comment}”</p>}
        </li>
      ))}
    </ol>
  )
}
