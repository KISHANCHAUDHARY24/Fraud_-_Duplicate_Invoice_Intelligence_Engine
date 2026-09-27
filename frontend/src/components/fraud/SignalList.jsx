import { Link } from 'react-router-dom'

const SEVERITY = {
  HIGH: 'bg-red-50 text-red-700 ring-red-200',
  MEDIUM: 'bg-amber-50 text-amber-800 ring-amber-200',
  LOW: 'bg-slate-100 text-slate-700 ring-slate-200',
  INFO: 'bg-slate-50 text-slate-500 ring-slate-200',
}

/** Every signal of an analysis: type, severity (as a word), points and message. */
export default function SignalList({ signals }) {
  if (!signals?.length) return <p className="text-sm text-slate-500">No signals were raised.</p>
  return (
    <ul className="divide-y divide-slate-100">
      {signals.map((signal) => (
        <li key={signal.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-800">{signal.label}</p>
            <p className="mt-0.5 text-sm text-slate-600">{signal.message}</p>
            {signal.related_invoice && (
              <Link to={`/invoices/${signal.related_invoice}`} className="mt-1 inline-block text-xs font-medium text-brand-700 hover:underline">
                Related invoice {signal.related_invoice_number || `#${signal.related_invoice}`}
              </Link>
            )}
          </div>
          <span className={`rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${SEVERITY[signal.severity] || SEVERITY.LOW}`}>
            {signal.severity.charAt(0) + signal.severity.slice(1).toLowerCase()} severity
          </span>
          <span className="w-12 text-right text-sm font-semibold text-slate-700 tabular-nums">+{signal.points}</span>
        </li>
      ))}
    </ul>
  )
}
