import { Link } from 'react-router-dom'

import { formatCurrency, formatDate } from '../../utils/format'
import RiskBadge from '../badges/RiskBadge'
import StatusBadge from '../badges/StatusBadge'
import SortHeader from '../common/SortHeader'

/** `compact` drops the date and department columns; `showVendor={false}` is for a single vendor's page. */
export default function InvoiceTable({ invoices, ordering, onSort, compact = false, showVendor = true }) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-sm ${compact ? 'min-w-[560px]' : 'min-w-[760px]'}`}>
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs text-slate-500">
          <tr>
            <SortHeader field="invoice_number" label="Invoice" ordering={ordering} onSort={onSort} />
            {showVendor && <SortHeader field="vendor__vendor_name" label="Vendor" ordering={ordering} onSort={onSort} />}
            <SortHeader field="amount" label="Amount" ordering={ordering} onSort={onSort} align="right" />
            {!compact && <SortHeader field="invoice_date" label="Invoice date" ordering={ordering} onSort={onSort} />}
            <SortHeader field="risk_score" label="Risk" ordering={ordering} onSort={onSort} />
            <SortHeader field="approval_status" label="Status" ordering={ordering} onSort={onSort} />
            {!compact && <th scope="col" className="px-4 py-3 text-left font-medium">Department</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {invoices.map((invoice) => (
            <tr key={invoice.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link to={`/invoices/${invoice.id}`} className="font-medium text-brand-700 hover:underline">
                  {invoice.invoice_number}
                </Link>
              </td>
              {showVendor && <td className="max-w-56 truncate px-4 py-3 text-slate-700" title={invoice.vendor_name}>{invoice.vendor_name}</td>}
              <td className="px-4 py-3 text-right font-medium text-slate-900 tabular-nums">
                {formatCurrency(invoice.amount, invoice.currency)}
              </td>
              {!compact && <td className="px-4 py-3 whitespace-nowrap text-slate-600">{formatDate(invoice.invoice_date)}</td>}
              <td className="px-4 py-3"><RiskBadge level={invoice.risk_level} score={invoice.risk_score} size="sm" /></td>
              <td className="px-4 py-3"><StatusBadge status={invoice.approval_status} /></td>
              {!compact && <td className="px-4 py-3 text-slate-600">{invoice.department || '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
