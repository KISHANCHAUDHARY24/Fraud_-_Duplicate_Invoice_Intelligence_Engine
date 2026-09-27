/** Filter bar for the invoice list. Values are plain strings from the URL query. */
import { RISK_OPTIONS, STATUS_OPTIONS } from '../../utils/invoiceOptions'
import { ClearFilters, FILTER_INPUT as inputClass, FilterField as Labelled, SearchInput } from '../common/Filters'

export default function InvoiceFilters({ values, onChange, onClear, vendors, searchText, onSearchText }) {
  const set = (key) => (event) => onChange({ [key]: event.target.value })
  const active = Object.entries(values).some(([key, value]) => key !== 'ordering' && key !== 'page' && value)
  return (
    <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-6">
      <SearchInput value={searchText} onChange={onSearchText} placeholder="Number, vendor, description, PO…"
        className="sm:col-span-2" />
      <Labelled label="Status">
        <select value={values.approval_status} onChange={set('approval_status')} className={inputClass}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </Labelled>
      <Labelled label="Risk">
        <select value={values.risk_level} onChange={set('risk_level')} className={inputClass}>
          <option value="">Any risk</option>
          {RISK_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </Labelled>
      <Labelled label="Vendor" className="lg:col-span-2">
        <select value={values.vendor} onChange={set('vendor')} className={inputClass}>
          <option value="">All vendors</option>
          {vendors.map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.vendor_name}</option>)}
        </select>
      </Labelled>
      <Labelled label="Invoice date from">
        <input type="date" value={values.date_from} onChange={set('date_from')} className={inputClass} />
      </Labelled>
      <Labelled label="Invoice date to">
        <input type="date" value={values.date_to} onChange={set('date_to')} className={inputClass} />
      </Labelled>
      <Labelled label="Amount from">
        <input type="number" min="0" inputMode="decimal" value={values.amount_min} onChange={set('amount_min')}
          placeholder="0" className={inputClass} />
      </Labelled>
      <Labelled label="Amount to">
        <input type="number" min="0" inputMode="decimal" value={values.amount_max} onChange={set('amount_max')}
          placeholder="Any" className={inputClass} />
      </Labelled>
      <div className="flex items-end sm:col-span-2">
        <ClearFilters visible={active} onClear={onClear} />
      </div>
    </div>
  )
}
