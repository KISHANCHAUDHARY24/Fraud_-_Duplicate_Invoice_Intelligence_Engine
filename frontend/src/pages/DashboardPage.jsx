/**
 * Dashboard (docs/frontend.md §6): KPI tiles, six charts and the high-risk invoice table.
 * Everything comes from one call, GET /api/dashboard/summary/, already scoped to the user's role.
 */
import {
  Ban, BrainCircuit, ClipboardCheck, Copy, Database, FileText, RefreshCw, Server, ShieldAlert, Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { fetchDashboardSummary } from '../api/dashboard'
import { fetchHealth } from '../api/system'
import {
  AlertsOverTimeChart, ApprovalTrendsChart, MonthlySpendingChart, RiskDistributionChart, StatusDistributionChart,
  VendorRiskChart,
} from '../components/charts/DashboardCharts'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import KpiCard from '../components/common/KpiCard'
import PageHeader from '../components/common/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import InvoiceTable from '../components/invoices/InvoiceTable'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { formatCurrency, formatDateTime } from '../utils/format'
import { Cap } from '../utils/permissions'

const PENDING_HINT = { all: 'All reviewers', mine: 'Waiting for your decision', my_invoices: 'Your invoices in review' }

function StatusDot({ ok }) {
  return <span className={`size-1.5 rounded-full ${ok ? 'bg-green-600' : 'bg-red-600'}`} aria-hidden />
}

function SystemStatus() {
  const { data: health, loading } = useAsync(fetchHealth)
  if (loading && !health) return null
  const ml = health?.ml_service
  const items = [
    [Server, 'Django API', Boolean(health)],
    [Database, 'Database', health?.database === 'ok'],
    [BrainCircuit, ml?.model_loaded ? `ML service · ${ml.model_version}` : 'ML service', ml?.status === 'ok'],
  ]
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500" aria-label="System status">
      {items.map(([Icon, label, ok]) => (
        <li key={label} className="flex items-center gap-1.5">
          <Icon className="size-3.5" aria-hidden />{label}<StatusDot ok={ok} />
          <span className="sr-only">{ok ? 'online' : 'unavailable'}</span>
        </li>
      ))}
    </ul>
  )
}

export default function DashboardPage() {
  const { user, can } = useAuth()
  const { data, error, loading, reload } = useAsync(fetchDashboardSummary)

  const header = (
    <PageHeader
      title={`Welcome, ${user.first_name || user.full_name}`}
      description={`${user.role_name || 'User'}${user.department ? ` · ${user.department}` : ''}${
        data ? ` · Updated ${formatDateTime(data.generated_at)}` : ''}`}
      actions={<Button variant="secondary" size="sm" icon={RefreshCw} onClick={reload} loading={loading && Boolean(data)}>Refresh</Button>}
    />
  )
  if (error) return <>{header}<Card><ErrorState error={error} onRetry={reload} /></Card></>
  if (!data) return <>{header}<LoadingState label="Loading dashboard…" /></>

  const { kpis } = data
  const pendingLink = can(Cap.APPROVALS_VIEW) ? '/approvals' : '/invoices?approval_status=UNDER_REVIEW'
  return (
    <>
      {header}
      <div className="mb-4"><SystemStatus /></div>

      <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard label="Total invoices" value={kpis.total_invoices.toLocaleString()} icon={FileText} to="/invoices" />
        <KpiCard label="Total spending" value={formatCurrency(kpis.total_spending)} icon={Wallet}
          hint="Submitted invoices; drafts and rejected excluded" />
        <KpiCard label="Suspicious invoices" value={kpis.suspicious_invoices.toLocaleString()} icon={ShieldAlert}
          tone="warning" hint="Medium risk or higher" to="/invoices?risk_level=MEDIUM,HIGH,CRITICAL&ordering=-risk_score" />
        <KpiCard label="Possible duplicates" value={kpis.possible_duplicates.toLocaleString()} icon={Copy} tone="warning"
          hint="Invoices with a duplicate signal" to="/fraud-alerts?type=DUPLICATE" />
        <KpiCard label="Pending approvals" value={kpis.pending_approvals.toLocaleString()} icon={ClipboardCheck}
          hint={PENDING_HINT[kpis.pending_approvals_scope]} to={pendingLink} />
        <KpiCard label="Blocked invoices" value={kpis.blocked_invoices.toLocaleString()} icon={Ban} tone="danger"
          hint="Payment held for investigation" to="/invoices?approval_status=BLOCKED" />
      </section>

      <section aria-label="Charts" className="mt-6 grid gap-6 [&>*]:min-w-0 lg:grid-cols-2">
        <MonthlySpendingChart data={data.monthly_spending} />
        <AlertsOverTimeChart data={data.alerts_over_time} />
        <RiskDistributionChart data={data.risk_distribution} />
        <StatusDistributionChart data={data.status_distribution} />
        <VendorRiskChart data={data.vendor_risk} />
        <ApprovalTrendsChart data={data.approval_trends} />
      </section>

      <Card className="mt-6" title="High-risk invoices" subtitle="High or critical risk, not yet rejected or paid"
        bodyClassName="p-0"
        actions={<Link to="/invoices?risk_level=HIGH,CRITICAL&ordering=-risk_score"
          className="text-sm font-medium text-brand-700 hover:underline">View all</Link>}>
        {data.high_risk_invoices.length ? (
          <InvoiceTable invoices={data.high_risk_invoices} compact />
        ) : (
          <EmptyState title="No high-risk invoices" message="Invoices scoring High or Critical will appear here." />
        )}
      </Card>
    </>
  )
}
