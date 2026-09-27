/**
 * One invoice: explained risk analysis, signals, possible duplicates, line items and history.
 * Actions depend on the user's capabilities AND the invoice status (e.g. only drafts can be edited).
 */
import { ArrowLeft, Banknote, Pencil, RefreshCw, Send, ShieldAlert, Trash2 } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { listApprovals, simulatePayment } from '../api/approvals'
import { listAlerts } from '../api/fraud'
import { deleteInvoice, getInvoice, invoiceHistory, reanalyzeInvoice, similarInvoices, submitInvoice } from '../api/invoices'
import ApprovalActions from '../components/approvals/ApprovalActions'
import RiskBadge from '../components/badges/RiskBadge'
import StatusBadge from '../components/badges/StatusBadge'
import Alert from '../components/common/Alert'
import Button, { ButtonLink } from '../components/common/Button'
import Card from '../components/common/Card'
import ConfirmDialog from '../components/common/ConfirmDialog'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import DuplicateComparison from '../components/fraud/DuplicateComparison'
import RiskAnalysisCard from '../components/fraud/RiskAnalysisCard'
import SignalList from '../components/fraud/SignalList'
import HistoryTimeline from '../components/invoices/HistoryTimeline'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { canDecide } from '../utils/approvals'
import { formatCurrency, formatDate, formatDateTime } from '../utils/format'
import { categoryLabel } from '../utils/invoiceOptions'
import { Cap } from '../utils/permissions'

const noRows = () => Promise.resolve({ results: [] })
const DECISION_MESSAGES = {
  approve: ['success', 'Approved. The payment is scheduled.'],
  reject: ['info', 'Rejected. The submitter has been notified with your reason.'],
  'request-clarification': ['info', 'Sent back to the submitter as a draft for clarification.'],
  escalate: ['info', 'Escalated. An auditor is now the reviewer.'],
}

const ROUTING_MESSAGES = {
  APPROVED: ['success', 'Approved automatically: low risk and within the approval threshold.'],
  UNDER_REVIEW: ['info', 'Sent for review. The assigned reviewer has been notified.'],
  BLOCKED: ['error', 'Payment blocked: critical risk. An auditor will investigate.'],
}

function Detail({ label, children }) {
  return (
    <div className="py-2.5">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{children || '—'}</dd>
    </div>
  )
}

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const { user, can } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [dialog, setDialog] = useState(null) // 'submit' | 'reanalyze' | 'delete' | 'pay'
  const [notice, setNotice] = useState(() => (location.state?.justCreated ? (
    location.state.submitted ? null : ['success', 'Invoice saved as a draft. Submit it when it is ready for analysis.']
  ) : null))

  const loadInvoice = useCallback(() => getInvoice(id), [id])
  const loadSimilar = useCallback(() => similarInvoices(id), [id])
  const loadHistory = useCallback(() => invoiceHistory(id), [id])
  // The reviewer's pending step (the API only returns steps assigned to the user, or all for Admins).
  const canSeeApprovals = can(Cap.APPROVALS_VIEW)
  const loadApproval = useCallback(
    () => (canSeeApprovals ? listApprovals({ invoice: id, decision: 'PENDING' }) : noRows()), [id, canSeeApprovals])
  const loadAlerts = useCallback(() => listAlerts({ invoice: id }), [id])
  const invoice = useAsync(loadInvoice)
  const similar = useAsync(loadSimilar)
  const history = useAsync(loadHistory)
  const approvals = useAsync(loadApproval)
  const alerts = useAsync(loadAlerts)

  const reloadAll = () => {
    invoice.reload()
    similar.reload()
    history.reload()
    approvals.reload()
    alerts.reload()
  }

  if (invoice.error) {
    return <Card><ErrorState error={invoice.error} onRetry={invoice.reload}
      title={invoice.error.status === 404 ? 'Invoice not found' : 'Could not load this invoice'} /></Card>
  }
  if (!invoice.data) return <LoadingState label="Loading invoice…" />

  const data = invoice.data
  const analysis = data.latest_analysis
  const isDraft = data.approval_status === 'DRAFT'
  const canSubmit = isDraft && can(Cap.INVOICES_SUBMIT)
  const canEdit = data.is_editable && can(Cap.INVOICES_CREATE)
  const canReanalyze = !isDraft && can(Cap.INVOICES_REANALYZE)
  const canPay = data.approval_status === 'APPROVED' && can(Cap.PAYMENTS_SIMULATE)
  const myApproval = approvals.data?.results.find((approval) => canDecide(approval, user, can))
  const fraudAlert = alerts.data?.results[0]  // newest first

  async function runSubmit() {
    const result = await submitInvoice(id)
    setNotice(ROUTING_MESSAGES[result.approval_status] || ['info', 'Analysis complete.'])
    reloadAll()
  }

  async function runReanalyze() {
    await reanalyzeInvoice(id)
    setNotice(['success', 'The analysis was run again. The new result is shown below.'])
    reloadAll()
  }

  async function runPayment() {
    const payment = await simulatePayment(id)
    setNotice(['success', `Payment simulated (reference ${payment.reference}). No money was moved.`])
    reloadAll()
  }

  async function runDelete() {
    await deleteInvoice(id)
    navigate('/invoices', { replace: true })
  }

  return (
    <>
      <Link to="/invoices" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden /> All invoices
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{data.invoice_number}</h1>
            <StatusBadge status={data.approval_status} />
            <RiskBadge level={data.risk_level} score={data.risk_score} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {data.vendor_name} · {formatCurrency(data.amount, data.currency)} · submitted by {data.submitted_by_name}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && <ButtonLink to={`/invoices/${id}/edit`} variant="secondary" icon={Pencil}>Edit</ButtonLink>}
          {canEdit && <Button variant="secondary" icon={Trash2} onClick={() => setDialog('delete')}>Delete</Button>}
          {canReanalyze && <Button variant="secondary" icon={RefreshCw} onClick={() => setDialog('reanalyze')}>Re-analyse</Button>}
          {fraudAlert && <ButtonLink to={`/fraud-alerts/${fraudAlert.id}`} variant="secondary" icon={ShieldAlert}>
            {fraudAlert.status === 'OPEN' || fraudAlert.status === 'IN_REVIEW' ? 'Investigation' : 'Closed alert'}</ButtonLink>}
          {canPay && <Button variant="secondary" icon={Banknote} onClick={() => setDialog('pay')}>Simulate payment</Button>}
          {canSubmit && <Button icon={Send} onClick={() => setDialog('submit')}>Submit for analysis</Button>}
        </div>
      </div>

      {notice && <Alert tone={notice[0]} className="mb-6">{notice[1]}</Alert>}
      {myApproval && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-brand-200 bg-brand-50 p-4">
          <div>
            <p className="font-medium text-slate-900">Your decision is needed</p>
            <p className="text-sm text-slate-600">
              {myApproval.level_label}. Read the risk analysis below before deciding; the score is a reason to check, not a verdict.
            </p>
          </div>
          <ApprovalActions approval={myApproval} onDone={(_, action) => {
            setNotice(DECISION_MESSAGES[action])
            reloadAll()
          }} />
        </div>
      )}
      {data.fraud_status === 'ANALYSIS_FAILED' && (
        <Alert tone="warning" className="mb-6" title="The fraud analysis could not run">
          The ML service was unavailable, so this invoice was sent to manual review.
          {canReanalyze && ' Use "Re-analyse" once the service is running again.'}
        </Alert>
      )}

      <div className="grid gap-6 [&>*]:min-w-0 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <RiskAnalysisCard analysis={analysis} emptyMessage={isDraft
            ? 'This draft has not been analysed yet. Submitting it runs duplicate detection, the fraud rules and the anomaly model.'
            : 'No analysis is available for this invoice.'} />

          {analysis?.signals?.length > 0 && (
            <Card title="Signals" subtitle="Each indicator, its severity and the points it added">
              <SignalList signals={analysis.signals} />
            </Card>
          )}

          {similar.data?.length > 0 && (
            <Card title="Possible duplicates" subtitle="Most similar earlier invoices, compared field by field">
              <div className="space-y-4">
                {similar.data.slice(0, 3).map((match) => (
                  <DuplicateComparison key={match.invoice.id} invoice={data} match={match} />
                ))}
              </div>
            </Card>
          )}

          {data.items?.length > 0 && (
            <Card title="Line items" bodyClassName="p-0">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <tr><th scope="col" className="px-5 py-2 font-medium">Description</th>
                    <th scope="col" className="px-5 py-2 text-right font-medium">Quantity</th>
                    <th scope="col" className="px-5 py-2 text-right font-medium">Unit price</th>
                    <th scope="col" className="px-5 py-2 text-right font-medium">Total</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {data.items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-5 py-2 text-slate-700">{item.description}</td>
                      <td className="px-5 py-2 text-right text-slate-700">{item.quantity}</td>
                      <td className="px-5 py-2 text-right text-slate-700">{formatCurrency(item.unit_price, data.currency)}</td>
                      <td className="px-5 py-2 text-right font-medium text-slate-900">{formatCurrency(item.line_total, data.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card title="Invoice details">
            <dl className="-my-2.5 divide-y divide-slate-100">
              <Detail label="Vendor">{data.vendor_name}</Detail>
              <Detail label="Amount">{formatCurrency(data.amount, data.currency)}{Number(data.tax) > 0 && ` (tax ${formatCurrency(data.tax, data.currency)})`}</Detail>
              <Detail label="Invoice date">{formatDate(data.invoice_date)}</Detail>
              <Detail label="Due date">{formatDate(data.due_date)}</Detail>
              <Detail label="Category">{categoryLabel(data.purchase_category)}</Detail>
              <Detail label="Department">{data.department}</Detail>
              <Detail label="Purchase order">{data.purchase_order_number}</Detail>
              <Detail label="Pay to account">
                {data.payment_bank_account && `${data.payment_bank_account.bank_name} ${data.payment_bank_account.masked_account}`}
              </Detail>
              <Detail label="Fraud review status">{data.fraud_status_label}</Detail>
              <Detail label="Submitted">{formatDateTime(data.submission_date)}</Detail>
              <Detail label="Description">{data.description}</Detail>
            </dl>
          </Card>
          <Card title="History" subtitle="From the audit log">
            {history.error ? <p className="text-sm text-red-600">{history.error.message}</p> : <HistoryTimeline entries={history.data} />}
          </Card>
        </div>
      </div>

      <ConfirmDialog open={dialog === 'submit'} onClose={() => setDialog(null)} onConfirm={runSubmit}
        title="Submit for analysis?" confirmLabel="Submit"
        message="The invoice is checked for duplicates, fraud rules and unusual patterns, then routed to the right reviewer. It can no longer be edited." />
      <ConfirmDialog open={dialog === 'reanalyze'} onClose={() => setDialog(null)} onConfirm={runReanalyze}
        title="Run the analysis again?" confirmLabel="Re-analyse"
        message="A new analysis is stored next to the previous one. The invoice's approval status does not change." />
      <ConfirmDialog open={dialog === 'pay'} onClose={() => setDialog(null)} onConfirm={runPayment}
        title="Simulate the payment?" confirmLabel="Mark as paid"
        message={`${data.invoice_number} is marked as paid with a simulated reference. This is a demonstration: no money is transferred.`} />
      <ConfirmDialog open={dialog === 'delete'} onClose={() => setDialog(null)} onConfirm={runDelete} tone="danger"
        title="Delete this draft?" confirmLabel="Delete draft"
        message={`${data.invoice_number} will be removed. The deletion is recorded in the audit log.`} />
    </>
  )
}
