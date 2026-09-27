/** The invoice's audit trail as a vertical timeline (read-only, from the append-only audit log). */
import { formatDateTime } from '../../utils/format'

export default function HistoryTimeline({ entries }) {
  if (!entries?.length) return <p className="text-sm text-slate-500">No history yet.</p>
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-5">
      {entries.map((entry) => (
        <li key={entry.id} className="relative">
          <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-white bg-brand-600 ring-1 ring-brand-200" aria-hidden />
          <p className="text-sm font-medium text-slate-800">{entry.action_label}</p>
          <p className="text-xs text-slate-500">{entry.user_name} · {formatDateTime(entry.timestamp)}</p>
          {entry.description && <p className="mt-0.5 text-xs text-slate-600">{entry.description}</p>}
        </li>
      ))}
    </ol>
  )
}
