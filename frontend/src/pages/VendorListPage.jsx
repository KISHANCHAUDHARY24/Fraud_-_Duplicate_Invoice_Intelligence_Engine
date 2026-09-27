/** Vendor list: search, status filter, sortable totals. Filters live in the URL like the invoice list. */
import { Building2, Plus } from 'lucide-react'
import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { listVendors } from '../api/vendors'
import StateBadge from '../components/badges/StateBadge'
import { ButtonLink } from '../components/common/Button'
import Card from '../components/common/Card'
import { ClearFilters, FilterSelect, SearchInput } from '../components/common/Filters'
import PageHeader from '../components/common/PageHeader'
import Pagination from '../components/common/Pagination'
import SortHeader from '../components/common/SortHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { paramsFrom, useUrlFilters } from '../hooks/useUrlFilters'
import { formatCurrency, formatDate } from '../utils/format'
import { Cap } from '../utils/permissions'
import { VENDOR_STATUS_OPTIONS } from '../utils/reviewOptions'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'status']
const DEFAULT_ORDERING = 'vendor_name'

function VendorTable({ vendors, ordering, onSort }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs text-slate-500">
          <tr>
            <SortHeader field="vendor_name" label="Vendor" ordering={ordering} onSort={onSort} />
            <SortHeader label="Status" />
            <SortHeader label="Bank account" />
            <SortHeader field="invoice_count" label="Invoices" ordering={ordering} onSort={onSort} align="right" />
            <SortHeader field="total_spending" label="Total spending" ordering={ordering} onSort={onSort} align="right" />
            <SortHeader field="created_at" label="Added" ordering={ordering} onSort={onSort} />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {vendors.map((vendor) => (
            <tr key={vendor.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link to={`/vendors/${vendor.id}`} className="font-medium text-brand-700 hover:underline">{vendor.vendor_name}</Link>
                {vendor.registration_number && <p className="text-xs text-slate-500">{vendor.registration_number}</p>}
              </td>
              <td className="px-4 py-3"><StateBadge kind="vendor" value={vendor.status} /></td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                {vendor.active_bank_account
                  ? <>{vendor.active_bank_account.bank_name} <span className="font-mono">{vendor.active_bank_account.masked_account}</span></>
                  : <span className="text-slate-400">None</span>}
              </td>
              <td className="px-4 py-3 text-right text-slate-700 tabular-nums">{vendor.invoice_count ?? '—'}</td>
              <td className="px-4 py-3 text-right font-medium text-slate-900 tabular-nums">{formatCurrency(vendor.total_spending)}</td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600">{formatDate(vendor.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function VendorListPage() {
  const { can } = useAuth()
  const { values, ordering, page, update, clear, searchText, setSearchText, queryKey } =
    useUrlFilters(FILTER_KEYS, { ordering: DEFAULT_ORDERING })
  const load = useCallback(
    () => listVendors(paramsFrom(queryKey, FILTER_KEYS, { ordering: DEFAULT_ORDERING, pageSize: PAGE_SIZE })),
    [queryKey])
  const { data, error, loading, reload } = useAsync(load)

  return (
    <>
      <PageHeader title="Vendors" description="Suppliers, their bank accounts and spending. Open a vendor to see its risk indicators."
        actions={can(Cap.VENDORS_CREATE) && <ButtonLink to="/vendors/new" icon={Plus}>New vendor</ButtonLink>} />
      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <SearchInput value={searchText} onChange={setSearchText} placeholder="Name, registration no., email, phone…"
            className="sm:col-span-2" />
          <FilterSelect label="Status" value={values.status} onChange={(status) => update({ status })}
            options={VENDOR_STATUS_OPTIONS} all="All statuses" />
          <div className="flex items-end"><ClearFilters visible={Boolean(values.search || values.status)} onClear={clear} /></div>
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <LoadingState label="Loading vendors…" />
        ) : data.count === 0 ? (
          <EmptyState icon={Building2} title="No vendors match" message="Try another search, or add a new vendor." />
        ) : (
          <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
            <VendorTable vendors={data.results} ordering={ordering} onSort={(value) => update({ ordering: value })} />
            <Pagination page={page} pageSize={PAGE_SIZE} count={data.count}
              onPage={(value) => update({ page: value > 1 ? String(value) : '' }, { resetPage: false })} />
          </div>
        )}
      </Card>
    </>
  )
}
