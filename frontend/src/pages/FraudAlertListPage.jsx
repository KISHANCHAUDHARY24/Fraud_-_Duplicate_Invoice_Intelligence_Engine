/**
 * Fraud alerts: invoices that need investigation. Opens on the alerts still open or in review;
 * "All" shows closed ones too. Everyone sees alerts of the invoices they may open.
 */
import { ShieldCheck } from 'lucide-react'
import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { listAlerts } from '../api/fraud'
import { vendorOptions } from '../api/vendors'
import RiskBadge from '../components/badges/RiskBadge'
import StateBadge from '../components/badges/StateBadge'
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
import { ALERT_STATUS_OPTIONS, SEVERITY_OPTIONS, SIGNAL_TYPE_OPTIONS, signalTypeLabel } from '../utils/reviewOptions'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'status', 'severity', 'type', 'vendor', 'assigned_to']
const DEFAULTS = { status: 'OPEN,IN_REVIEW' }
const DEFAULT_ORDERING = '-created_at'

function AlertTable({ alerts, ordering, onSort }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs text-slate-500">
          <tr>
            <SortHeader field="created_at" label="Raised" ordering={ordering} onSort={onSort} />
            <SortHeader label="Invoice" />
            <SortHeader label="Vendor" />
            <SortHeader label="Amount" align="right" />
            <SortHeader field="invoice__risk_score" label="Risk" ordering={ordering} onSort={onSort} />
            <SortHeader label="Indicators" />
            <SortHeader field="status" label="Status" ordering={ordering} onSort={onSort} />
            <SortHeader label="Assigned to" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {alerts.map((alert) => {
            const others = alert.signal_types.filter((type) => type !== alert.primary_type)
            return (
              <tr key={alert.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 whitespace-nowrap">
                  <Link to={`/fraud-alerts/${alert.id}`} className="font-medium text-brand-700 hover:underline">
                    Alert #{alert.id}
                  </Link>
                  <p className="text-xs text-slate-500">{formatDate(alert.created_at)}</p>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/invoices/${alert.invoice}`} className="text-slate-700 hover:underline">{alert.invoice_number}</Link>
                </td>
                <td className="max-w-48 truncate px-4 py-3 text-slate-700" title={alert.vendor_name}>{alert.vendor_name}</td>
                <td className="px-4 py-3 text-right font-medium text-slate-900 tabular-nums">{formatCurrency(alert.amount)}</td>
                <td className="px-4 py-3"><RiskBadge level={alert.severity} score={alert.risk_score} size="sm" /></td>
                <td className="px-4 py-3 text-slate-700">
                  {alert.primary_type_label}
                  {others.length > 0 && (
                    <span className="text-slate-500" title={others.map(signalTypeLabel).join(', ')}> +{others.length} more</span>
                  )}
                </td>
                <td className="px-4 py-3"><StateBadge kind="alert" value={alert.status} /></td>
                <td className="px-4 py-3 text-slate-600">{alert.assigned_to_name || <span className="text-slate-400">Unassigned</span>}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function FraudAlertListPage() {
  const { user, can } = useAuth()
  const { values, ordering, page, update, clear, searchText, setSearchText, queryKey } =
    useUrlFilters(FILTER_KEYS, { ordering: DEFAULT_ORDERING, defaults: DEFAULTS })
  const load = useCallback(
    () => listAlerts(paramsFrom(queryKey, FILTER_KEYS, { ordering: DEFAULT_ORDERING, defaults: DEFAULTS, pageSize: PAGE_SIZE })),
    [queryKey])
  const { data, error, loading, reload } = useAsync(load)
  const { data: vendors } = useAsync(vendorOptions)
  const isInvestigator = can(Cap.ALERTS_RESOLVE)
  const filtered = Boolean(values.search || values.severity || values.type || values.vendor || values.assigned_to
    || values.status !== DEFAULTS.status)

  return (
    <>
      <PageHeader title="Fraud alerts"
        description="Invoices with medium or higher risk. Each alert is a reason to look closer, not a finding of fraud." />
      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-6">
          <SearchInput value={searchText} onChange={setSearchText} placeholder="Invoice number or vendor…" className="sm:col-span-2" />
          <FilterSelect label="Status" value={values.status} onChange={(status) => update({ status })}
            options={ALERT_STATUS_OPTIONS} all="All statuses" />
          <FilterSelect label="Severity" value={values.severity} onChange={(severity) => update({ severity })}
            options={SEVERITY_OPTIONS} all="Any severity" />
          <FilterSelect label="Indicator" value={values.type} onChange={(type) => update({ type })}
            options={SIGNAL_TYPE_OPTIONS} all="Any indicator" className="sm:col-span-2" />
          <FilterSelect label="Vendor" value={values.vendor} onChange={(vendor) => update({ vendor })}
            options={(vendors || []).map((vendor) => [String(vendor.id), vendor.vendor_name])} all="All vendors" className="sm:col-span-2" />
          {isInvestigator && (
            <FilterSelect label="Assigned to" value={values.assigned_to} onChange={(assigned) => update({ assigned_to: assigned })}
              options={[[String(user.id), 'Me']]} all="Anyone" />
          )}
          <div className="flex items-end"><ClearFilters visible={filtered} onClear={clear} /></div>
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <LoadingState label="Loading alerts…" />
        ) : data.count === 0 ? (
          <EmptyState icon={ShieldCheck} title={filtered ? 'No alerts match' : 'No open alerts'}
            message={filtered ? 'Try removing a filter.' : 'Nothing is waiting for investigation right now.'} />
        ) : (
          <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
            <AlertTable alerts={data.results} ordering={ordering} onSort={(value) => update({ ordering: value })} />
            <Pagination page={page} pageSize={PAGE_SIZE} count={data.count}
              onPage={(value) => update({ page: value > 1 ? String(value) : '' }, { resetPage: false })} />
          </div>
        )}
      </Card>
    </>
  )
}
