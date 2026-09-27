/**
 * Everything needed to investigate one alert on one screen (GET /api/fraud/alerts/{id}/):
 * the explained score, signals, possible duplicates, the vendor's profile and history,
 * the approval steps and the audit trail, plus the investigation actions.
 */
import { ArrowLeft, Building2, FileText } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getInvestigation } from '../api/fraud'
import ApprovalTimeline from '../components/approvals/ApprovalTimeline'
import RiskBadge from '../components/badges/RiskBadge'
import StateBadge from '../components/badges/StateBadge'
import StatusBadge from '../components/badges/StatusBadge'
import Alert from '../components/common/Alert'
import { ButtonLink } from '../components/common/Button'
import Card from '../components/common/Card'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import AlertActions from '../components/fraud/AlertActions'
import DuplicateComparison from '../components/fraud/DuplicateComparison'
import RiskAnalysisCard from '../components/fraud/RiskAnalysisCard'
import SignalList from '../components/fraud/SignalList'
import HistoryTimeline from '../components/invoices/HistoryTimeline'
import InvoiceTable from '../components/invoices/InvoiceTable'
import { useAsync } from '../hooks/useAsync'
import { formatCurrency, formatDate, formatDateTime } from '../utils/format'

const DONE = {
  IN_REVIEW: 'The alert is now in review.',
  RESOLVED: 'The alert is resolved. The invoice status below reflects the outcome.',
}

function Fact({ label, children }) {
  return (
    <div className="flex justify-between gap-3 py-2 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{children}</dd>
    </div>
  )
}

function VendorCard({ vendor }) {
  return (
    <Card title="Vendor" actions={<ButtonLink to={`/vendors/${vendor.id}`} variant="ghost" size="sm" icon={Building2}>Open</ButtonLink>}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="font-medium text-slate-900">{vendor.vendor_name}</p>
        <StateBadge kind="vendor" value={vendor.status} />
      </div>
      <dl className="-my-2 divide-y divide-slate-100">
        <Fact label="Invoices">{vendor.total_invoices}</Fact>
        <Fact label="Total spending">{formatCurrency(vendor.total_spending)}</Fact>
        <Fact label="Average invoice">{formatCurrency(vendor.average_invoice)}</Fact>
        <Fact label="Alerts (open)">{vendor.alert_count} ({vendor.open_alert_count})</Fact>
        <Fact label="Pays to">
          {vendor.active_bank_account
            ? <>{vendor.active_bank_account.bank_name} <span className="font-mono">{vendor.active_bank_account.masked_account}</span></>
            : 'No account'}
        </Fact>
      </dl>
      {vendor.risk_indicators.length > 0 && (
        <div className="mt-4 rounded-lg bg-amber-50 p-3">
          <p className="text-xs font-medium text-amber-900">Vendor risk indicators</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-amber-900">
            {vendor.risk_indicators.map((text) => <li key={text}>{text}</li>)}
          </ul>
        </div>
      )}
    </Card>
  )
}

function Resolution({ alert }) {
  const confirmed = alert.outcome === 'CONFIRMED_ISSUE'
  if (alert.status === 'DISMISSED') {
    return (
      <Alert tone="info" className="mb-6" title="Closed by the reviewer's decision">
        {alert.resolution_note || 'The invoice was decided in the approval workflow.'}
        {alert.resolved_by_name && ` (${alert.resolved_by_name}, ${formatDateTime(alert.resolved_at)})`}
      </Alert>
    )
  }
  return (
    <Alert tone={confirmed ? 'error' : 'success'} className="mb-6"
      title={confirmed ? 'Investigation outcome: issue confirmed' : 'Investigation outcome: cleared'}>
      “{alert.resolution_note}” · {alert.resolved_by_name}, {formatDateTime(alert.resolved_at)}
    </Alert>
  )
}

export default function FraudInvestigationPage() {
  const { id } = useParams()
  const load = useCallback(() => getInvestigation(id), [id])
  const { data, error, reload } = useAsync(load)
  const [notice, setNotice] = useState(null)

  if (error) {
    return <Card><ErrorState error={error} onRetry={reload}
      title={error.status === 404 ? 'Alert not found' : 'Could not load this alert'} /></Card>
  }
  if (!data) return <LoadingState label="Loading investigation…" />

  const { alert, invoice, vendor } = data
  const analysis = invoice.latest_analysis
  const onChanged = (updated) => {
    setNotice(DONE[updated?.status] || 'Saved.')
    reload()
  }

  return (
    <>
      <Link to="/fraud-alerts" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden /> All alerts
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Alert #{alert.id}: {alert.primary_type_label}</h1>
            <RiskBadge level={alert.severity} score={alert.risk_score} />
            <StateBadge kind="alert" value={alert.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            <Link to={`/invoices/${invoice.id}`} className="font-medium text-brand-700 hover:underline">{invoice.invoice_number}</Link>
            {' '}· {vendor.vendor_name} · {formatCurrency(invoice.amount, invoice.currency)} · raised {formatDate(alert.created_at)}
            {' '}· {alert.assigned_to_name ? `assigned to ${alert.assigned_to_name}` : 'unassigned'}
          </p>
          <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">Invoice status: <StatusBadge status={invoice.approval_status} /></p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink to={`/invoices/${invoice.id}`} variant="secondary" icon={FileText}>Open invoice</ButtonLink>
          <AlertActions alert={alert} invoice={invoice} onChanged={onChanged} />
        </div>
      </div>

      {notice && <Alert tone="success" className="mb-6">{notice}</Alert>}
      {alert.status === 'RESOLVED' || alert.status === 'DISMISSED' ? <Resolution alert={alert} /> : null}

      <div className="grid gap-6 [&>*]:min-w-0 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <RiskAnalysisCard analysis={analysis} />
          {analysis?.signals?.length > 0 && (
            <Card title="Signals" subtitle="Each indicator, its severity and the points it added">
              <SignalList signals={analysis.signals} />
            </Card>
          )}
          {data.similar_invoices.length > 0 && (
            <Card title="Possible duplicates" subtitle="Most similar earlier invoices, compared field by field">
              <div className="space-y-4">
                {data.similar_invoices.slice(0, 3).map((match) => (
                  <DuplicateComparison key={match.invoice.id} invoice={invoice} match={match} />
                ))}
              </div>
            </Card>
          )}
          <Card title="Vendor history" subtitle="This vendor's other recent invoices, for comparison" bodyClassName="p-0">
            {data.vendor_history.length
              ? <InvoiceTable invoices={data.vendor_history} compact showVendor={false} />
              : <EmptyState icon={FileText} title="No other invoices from this vendor" />}
          </Card>
        </div>
        <div className="space-y-6">
          <VendorCard vendor={vendor} />
          <Card title="Approval steps"><ApprovalTimeline approvals={data.approval_history} /></Card>
          <Card title="History" subtitle="From the audit log, newest first">
            <HistoryTimeline entries={[...data.audit_history].reverse()} />
          </Card>
        </div>
      </div>
    </>
  )
}
