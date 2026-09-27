/**
 * One vendor: risk indicators, totals, monthly spending, risk mix, bank-account history and recent invoices.
 * Totals cover all of the vendor's invoices; the recent-invoice list only shows invoices the user may open.
 */
import { AlertTriangle, ArrowLeft, Banknote, Calculator, FileText, Pencil, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'

import { vendorDashboard } from '../api/vendors'
import StateBadge from '../components/badges/StateBadge'
import { MonthlySpendingChart, RiskDistributionChart } from '../components/charts/DashboardCharts'
import { fillMonths } from '../components/charts/chartTheme'
import Alert from '../components/common/Alert'
import { ButtonLink } from '../components/common/Button'
import Card from '../components/common/Card'
import KpiCard from '../components/common/KpiCard'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import InvoiceTable from '../components/invoices/InvoiceTable'
import BankAccountPanel from '../components/vendors/BankAccountPanel'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { formatCurrency } from '../utils/format'
import { Cap } from '../utils/permissions'

const LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

export default function VendorDashboardPage() {
  const { id } = useParams()
  const { can } = useAuth()
  const load = useCallback(() => vendorDashboard(id), [id])
  const { data, error, reload } = useAsync(load)

  if (error) {
    return <Card><ErrorState error={error} onRetry={reload}
      title={error.status === 404 ? 'Vendor not found' : 'Could not load this vendor'} /></Card>
  }
  if (!data) return <LoadingState label="Loading vendor…" />

  const { vendor } = data
  const riskRows = LEVELS.map((level) => ({ level, count: data.risk_distribution[level] || 0 }))

  return (
    <>
      <Link to="/vendors" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden /> All vendors
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{vendor.vendor_name}</h1>
            <StateBadge kind="vendor" value={vendor.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {[vendor.registration_number, vendor.email, vendor.phone].filter(Boolean).join(' · ') || 'No contact details'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink to={`/invoices?vendor=${vendor.id}`} variant="secondary" icon={FileText}>Invoices</ButtonLink>
          <ButtonLink to={`/fraud-alerts?vendor=${vendor.id}&status=`} variant="secondary" icon={ShieldAlert}>Alerts</ButtonLink>
          {can(Cap.VENDORS_EDIT) && <ButtonLink to={`/vendors/${vendor.id}/edit`} variant="secondary" icon={Pencil}>Edit</ButtonLink>}
        </div>
      </div>

      {data.risk_indicators.length > 0 ? (
        <Alert tone="warning" title="Risk indicators for this vendor" className="mb-6">
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {data.risk_indicators.map((indicator) => <li key={indicator}>{indicator}</li>)}
          </ul>
          <p className="mt-2 text-xs">Indicators call for a closer look. They are not a finding of fraud.</p>
        </Alert>
      ) : (
        <Alert tone="success" className="mb-6">No risk indicators for this vendor right now.</Alert>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Invoices" value={data.total_invoices} hint={`${data.submitted_invoices} counted in spending`} icon={FileText} />
        <KpiCard label="Total spending" value={formatCurrency(data.total_spending)} hint="Drafts and rejected invoices excluded" icon={Banknote} />
        <KpiCard label="Average invoice" value={formatCurrency(data.average_invoice)} icon={Calculator} />
        <KpiCard label="Open alerts" value={data.open_alert_count} hint={`${data.alert_count} alert(s) in total`}
          icon={data.open_alert_count ? AlertTriangle : ShieldCheck} tone={data.open_alert_count ? 'warning' : 'default'}
          to={data.open_alert_count ? `/fraud-alerts?vendor=${vendor.id}` : undefined} />
      </div>

      <div className="mb-6 grid gap-6 [&>*]:min-w-0 lg:grid-cols-2">
        <MonthlySpendingChart data={fillMonths(data.monthly_spending)} title="Monthly spending"
          subtitle="This vendor, last 12 months (drafts and rejected excluded)" />
        <RiskDistributionChart data={riskRows} title="Risk of this vendor's invoices"
          subtitle="Analysed invoices by risk level (darker = more severe)" />
      </div>

      <div className="grid gap-6 [&>*]:min-w-0 lg:grid-cols-3">
        <Card title="Recent invoices" subtitle="The 10 most recent you have access to" bodyClassName="p-0" className="lg:col-span-2">
          {data.recent_invoices.length
            ? <InvoiceTable invoices={data.recent_invoices} compact showVendor={false} />
            : <EmptyState icon={FileText} title="No invoices to show" />}
        </Card>
        <Card title="Bank accounts" subtitle="Only the last 4 digits are shown">
          {can(Cap.BANK_ACCOUNTS_VIEW) || can(Cap.BANK_ACCOUNTS_MANAGE) ? (
            <BankAccountPanel vendorId={vendor.id} accounts={data.bank_accounts}
              canManage={can(Cap.BANK_ACCOUNTS_MANAGE)} onChanged={reload} />
          ) : (
            <p className="text-sm text-slate-500">Bank details are visible to Admins, Auditors and AP Officers.</p>
          )}
        </Card>
      </div>
    </>
  )
}
