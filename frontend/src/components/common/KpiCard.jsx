/** A stat tile: sentence-case label, one prominent value, optional hint and link. */
import { Link } from 'react-router-dom'

export default function KpiCard({ label, value, hint, icon: Icon, to, tone = 'default' }) {
  const toneRing = { default: 'bg-brand-50 text-brand-700', warning: 'bg-amber-50 text-amber-700', danger: 'bg-red-50 text-red-700' }[tone]
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-500">{label}</p>
        {Icon && (
          <span className={`flex size-8 items-center justify-center rounded-lg ${toneRing}`}>
            <Icon className="size-4" aria-hidden />
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </>
  )
  const className = 'block rounded-xl border border-slate-200 bg-white p-5 shadow-sm'
  return to ? (
    <Link to={to} className={`${className} transition-colors hover:border-brand-500`}>{body}</Link>
  ) : (
    <div className={className}>{body}</div>
  )
}
