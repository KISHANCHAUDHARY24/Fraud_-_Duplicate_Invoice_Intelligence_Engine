/**
 * Invoice list: search, filters, sorting and pagination, all kept in the URL query string
 * so refresh, the back button and shared links keep the same view.
 */
import { FileText, Plus } from 'lucide-react'
import { useCallback } from 'react'

import { listInvoices } from '../api/invoices'
import { vendorOptions } from '../api/vendors'
import { ButtonLink } from '../components/common/Button'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import Pagination from '../components/common/Pagination'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import InvoiceFilters from '../components/invoices/InvoiceFilters'
import InvoiceTable from '../components/invoices/InvoiceTable'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { paramsFrom, useUrlFilters } from '../hooks/useUrlFilters'
import { Cap } from '../utils/permissions'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'approval_status', 'risk_level', 'vendor', 'date_from', 'date_to', 'amount_min', 'amount_max']
const DEFAULT_ORDERING = '-submission_date'
const noVendors = []

export default function InvoiceListPage() {
  const { can } = useAuth()
  const { values: query, ordering, page, update, clear, searchText, setSearchText, queryKey } =
    useUrlFilters(FILTER_KEYS, { ordering: DEFAULT_ORDERING })
  const load = useCallback(
    () => listInvoices(paramsFrom(queryKey, FILTER_KEYS, { ordering: DEFAULT_ORDERING, pageSize: PAGE_SIZE })),
    [queryKey])
  const { data, error, loading, reload } = useAsync(load)
  const { data: vendors } = useAsync(vendorOptions)

  return (
    <>
      <PageHeader title="Invoices" description="Search, filter and open any invoice you have access to."
        actions={can(Cap.INVOICES_CREATE) && (
          <ButtonLink to="/invoices/upload" icon={Plus}>Upload invoice</ButtonLink>
        )} />
      <Card bodyClassName="p-0">
        <InvoiceFilters values={query} onChange={update} onClear={clear} vendors={vendors || noVendors}
          searchText={searchText} onSearchText={setSearchText} />
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <LoadingState label="Loading invoices…" />
        ) : data.count === 0 ? (
          <EmptyState icon={FileText} title="No invoices match"
            message="Try removing a filter, or upload a new invoice." />
        ) : (
          <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
            <InvoiceTable invoices={data.results} ordering={ordering} onSort={(value) => update({ ordering: value })} />
            <Pagination page={page} pageSize={PAGE_SIZE} count={data.count}
              onPage={(value) => update({ page: value > 1 ? String(value) : '' }, { resetPage: false })} />
          </div>
        )}
      </Card>
    </>
  )
}
