/**
 * Side-by-side comparison of an invoice with a possible duplicate (docs/duplicate-detection.md).
 * Each field shows both values and how similar they are, as a percentage and a meter.
 */
import { Check } from 'lucide-react'
import { Link } from 'react-router-dom'

import { formatCurrency, formatDate } from '../../utils/format'
import StatusBadge from '../badges/StatusBadge'

const FIELDS = [
  ['invoice_number', 'Invoice number', (inv) => inv.invoice_number],
  ['vendor', 'Vendor', (inv) => inv.vendor_name],
  ['amount', 'Amount', (inv) => formatCurrency(inv.amount, inv.currency)],
  ['date', 'Invoice date', (inv) => formatDate(inv.invoice_date)],
  ['description', 'Description', (inv) => inv.description],
]
const STRONG = 0.9

function Similarity({ value }) {
  const percent = Math.round((value ?? 0) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100" aria-hidden>
        <div className="h-full rounded-full bg-brand-600" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-xs text-slate-600 tabular-nums">{percent}%</span>
      {value >= STRONG && <Check className="size-3.5 text-slate-700" aria-label="Strong match" />}
    </div>
  )
}

export default function DuplicateComparison({ invoice, match }) {
  const other = { ...match.invoice, description: match.description }
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 px-4 py-2.5">
        <p className="text-sm font-medium text-slate-800">
          {match.score}% similar to{' '}
          <Link to={`/invoices/${other.id}`} className="text-brand-700 hover:underline">{other.invoice_number}</Link>
        </p>
        <StatusBadge status={other.approval_status} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
              <th scope="col" className="px-4 py-2 font-medium">Field</th>
              <th scope="col" className="px-4 py-2 font-medium">This invoice</th>
              <th scope="col" className="px-4 py-2 font-medium">Possible duplicate</th>
              <th scope="col" className="px-4 py-2 font-medium">Similarity</th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(([key, label, read]) => {
              const strong = match.components?.[key] >= STRONG
              return (
                <tr key={key} className={`border-b border-slate-50 align-top ${strong ? 'bg-amber-50/40' : ''}`}>
                  <th scope="row" className="px-4 py-2 text-left font-medium text-slate-600">{label}</th>
                  <td className="px-4 py-2 text-slate-800">{read(invoice)}</td>
                  <td className="px-4 py-2 text-slate-800">{read(other)}</td>
                  <td className="px-4 py-2"><Similarity value={match.components?.[key]} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
