/**
 * Approval queue. Managers and Auditors see the steps assigned to them (riskiest first by default);
 * Admins see every step but do not decide. Decisions are made here or on the invoice page.
 */
import { ClipboardCheck, Eye } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { listApprovals } from '../api/approvals'
import ApprovalActions from '../components/approvals/ApprovalActions'
import RiskBadge from '../components/badges/RiskBadge'
import StateBadge from '../components/badges/StateBadge'
import Alert from '../components/common/Alert'
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
import { formatCurrency, formatDate, formatDateTime } from '../utils/format'
import { DECISION_OPTIONS, LEVEL_OPTIONS } from '../utils/reviewOptions'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'decision', 'level']
const DEFAULTS = { decision: 'PENDING' }
const DEFAULT_ORDERING = '-invoice__risk_score'
const DONE_MESSAGES = {
  approve: 'approved. Payment is scheduled.',
  reject: 'rejected. The submitter has been notified.',
  'request-clarification': 'sent back to the submitter for clarification.',
  escalate: 'escalated to an auditor.',
}

function ApprovalTable({ approvals, ordering, onSort, showReviewer, onDone }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[780px] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs text-slate-500">
          <tr>
            <SortHeader label="Invoice" />
            <SortHeader field="invoice__amount" label="Amount" ordering={ordering} onSort={onSort} align="right" />
            <SortHeader field="invoice__risk_score" label="Risk" ordering={ordering} onSort={onSort} />
            <SortHeader field="created_at" label="Level · received" ordering={ordering} onSort={onSort} />
            {showReviewer && <SortHeader label="Reviewer" />}
            <SortHeader label="Decision" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {approvals.map((approval) => (
            <tr key={approval.id} className="align-top hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link to={`/invoices/${approval.invoice}`} className="font-medium text-brand-700 hover:underline">
                  {approval.invoice_number}
                </Link>
                <p className="max-w-52 truncate text-xs text-slate-500" title={approval.vendor_name}>
                  {approval.vendor_name} · by {approval.submitted_by_name}
                </p>
              </td>
              <td className="px-4 py-3 text-right font-medium text-slate-900 tabular-nums">
                {formatCurrency(approval.amount, approval.currency)}
              </td>
              <td className="px-4 py-3"><RiskBadge level={approval.risk_level} score={approval.risk_score} size="sm" /></td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                {approval.level_label}
                <p className="text-xs text-slate-500">{formatDate(approval.created_at)}</p>
              </td>
              {showReviewer && <td className="px-4 py-3 text-slate-600">{approval.assigned_to_name || '—'}</td>}
              <td className="w-px px-4 py-3 whitespace-nowrap">
                {approval.decision === 'PENDING' && (
                  <div className="flex items-center gap-2">
                    <ButtonLink to={`/invoices/${approval.invoice}`} variant="secondary" size="sm" icon={Eye}>Open</ButtonLink>
                    <ApprovalActions approval={approval} compact onDone={onDone} />
                  </div>
                )}
                {(approval.decision !== 'PENDING' || showReviewer) && (
                  <div className="space-y-1">
                    <StateBadge kind="decision" value={approval.decision} />
                    {approval.decided_at && (
                      <p className="text-xs text-slate-500">{approval.decided_by_name} · {formatDateTime(approval.decided_at)}</p>
                    )}
                    {approval.comment && <p className="max-w-64 truncate text-xs text-slate-600" title={approval.comment}>“{approval.comment}”</p>}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ApprovalQueuePage() {
  const { user } = useAuth()
  const isAdmin = user.role === 'ADMIN'
  const [notice, setNotice] = useState(null)
  const { values, ordering, page, update, clear, searchText, setSearchText, queryKey } =
    useUrlFilters(FILTER_KEYS, { ordering: DEFAULT_ORDERING, defaults: DEFAULTS })
  const load = useCallback(
    () => listApprovals(paramsFrom(queryKey, FILTER_KEYS, { ordering: DEFAULT_ORDERING, defaults: DEFAULTS, pageSize: PAGE_SIZE })),
    [queryKey])
  const { data, error, loading, reload } = useAsync(load)
  const filtered = Boolean(values.search || values.level || values.decision !== DEFAULTS.decision)
  const pendingView = values.decision === 'PENDING'

  const onDone = (approval, action) => {
    setNotice(`${approval.invoice_number} ${DONE_MESSAGES[action]}`)
    reload()
  }

  return (
    <>
      <PageHeader title="Approvals"
        description={isAdmin ? 'Every approval step in the system. Reviewers decide; Admins can follow progress here.'
          : 'Invoices waiting for your decision, riskiest first. Open an invoice to see why it was flagged.'} />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-5">
          <SearchInput value={searchText} onChange={setSearchText} placeholder="Invoice number or vendor…" className="sm:col-span-2" />
          <FilterSelect label="Decision" value={values.decision} onChange={(decision) => update({ decision })}
            options={isAdmin ? [['PENDING', 'Pending'], ...DECISION_OPTIONS.slice(1)] : DECISION_OPTIONS} all="All decisions" />
          <FilterSelect label="Review level" value={values.level} onChange={(level) => update({ level })}
            options={LEVEL_OPTIONS} all="All levels" />
          <div className="flex items-end"><ClearFilters visible={filtered} onClear={clear} /></div>
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <LoadingState label="Loading approvals…" />
        ) : data.count === 0 ? (
          <EmptyState icon={ClipboardCheck} title={pendingView && !filtered ? 'Nothing is waiting for you' : 'No approvals match'}
            message={pendingView && !filtered ? 'New invoices routed to you will appear here, and you will get a notification.'
              : 'Try another filter.'} />
        ) : (
          <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
            <ApprovalTable approvals={data.results} ordering={ordering} onSort={(value) => update({ ordering: value })}
              showReviewer={isAdmin} onDone={onDone} />
            <Pagination page={page} pageSize={PAGE_SIZE} count={data.count}
              onPage={(value) => update({ page: value > 1 ? String(value) : '' }, { resetPage: false })} />
          </div>
        )}
      </Card>
    </>
  )
}
