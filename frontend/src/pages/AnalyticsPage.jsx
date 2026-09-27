/**
 * Analytics for a chosen period (GET /api/analytics/): headline figures, trends, risk mix, the
 * indicators that fire most, vendor risk, spending by department and category, and approval times.
 * The period lives in the URL, so a view can be bookmarked or shared.
 */
import { AlarmClock, Banknote, Bot, Calculator, Copy, FileText, ShieldAlert, TriangleAlert } from 'lucide-react'
import { useCallback } from 'react'

import { fetchAnalytics } from '../api/analytics'
import { RankedBarChart, RiskTrendChart } from '../components/charts/AnalyticsCharts'
import { MonthlySpendingChart, RiskDistributionChart, VendorRiskChart } from '../components/charts/DashboardCharts'
import { formatCompactMoney } from '../components/charts/chartTheme'
import Card from '../components/common/Card'
import DateRangeFilter from '../components/common/DateRangeFilter'
import KpiCard from '../components/common/KpiCard'
import PageHeader from '../components/common/PageHeader'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import { useAsync } from '../hooks/useAsync'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { rangeError } from '../utils/dateRanges'
import { formatCurrency, formatDate } from '../utils/format'

const FILTER_KEYS = ['date_from', 'date_to']
const money = (value) => formatCurrency(value)
const percent = (value) => `${value}%`
const hours = (value) => (value === null || value === undefined ? '—' : value < 48 ? `${value} h` : `${(value / 24).toFixed(1)} days`)

export default function AnalyticsPage() {
  const { values, update, queryKey } = useUrlFilters(FILTER_KEYS)
  const invalid = rangeError(values.date_from, values.date_to)
  const load = useCallback(() => {
    const current = new URLSearchParams(queryKey)
    return fetchAnalytics({ date_from: current.get('date_from'), date_to: current.get('date_to') })
  }, [queryKey])
  // An impossible range is shown as a field error; the last good figures stay on screen.
  const { data, error, loading, reload } = useAsync(invalid ? pendingForever : load)

  return (
    <>
      <PageHeader title="Analytics" description="Spending, risk and approval figures for a period. Only invoices you have access to are counted." />
      <Card className="mb-6">
        <DateRangeFilter dateFrom={values.date_from} dateTo={values.date_to} onChange={(range) => update(range)} />
        {data && (
          <p className="mt-3 text-xs text-slate-500">
            Showing {formatDate(data.range.date_from)} – {formatDate(data.range.date_to)}. Invoices are counted by invoice date,
            alerts by the date they were raised, decisions by the date they were made.
          </p>
        )}
      </Card>

      {error ? (
        <Card><ErrorState error={error} onRetry={reload} /></Card>
      ) : !data ? (
        <LoadingState label="Calculating analytics…" />
      ) : (
        <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
          <Summary summary={data.summary} />
          <div className="grid gap-6 [&>*]:min-w-0 lg:grid-cols-2">
            <MonthlySpendingChart data={data.monthly} title="Spending per month"
              subtitle="Submitted invoices by invoice date (drafts and rejected excluded)" />
            <RiskTrendChart data={data.monthly} />
            <RiskDistributionChart data={data.risk_distribution} subtitle="Invoices in the period by risk level (darker = more severe)" />
            <RankedBarChart title="Indicators that fire most" subtitle="Invoices in the period with each risk signal"
              rows={data.signal_frequency} valueKey="invoices" valueName="Invoices" labelWidth={168}
              emptyMessage="No risk signals in this period."
              columns={[{ key: 'label', label: 'Indicator' }, { key: 'invoices', label: 'Invoices', align: 'right' },
                { key: 'average_points', label: 'Avg. points', align: 'right' }]} />
            <VendorRiskChart data={data.vendor_risk} subtitle="Average risk score of each vendor's invoices in the period (top 10)" />
            <RankedBarChart title="Spending by department" subtitle="Top 10 departments (drafts and rejected excluded)"
              rows={data.department_spending} valueKey="total" valueName="Spending" format={formatCompactMoney}
              columns={[{ key: 'label', label: 'Department' }, { key: 'count', label: 'Invoices', align: 'right' },
                { key: 'total', label: 'Spending', align: 'right', format: money }]} />
            <RankedBarChart title="Spending by category" subtitle="Purchase categories (drafts and rejected excluded)"
              rows={data.category_spending} valueKey="total" valueName="Spending" format={formatCompactMoney}
              columns={[{ key: 'label', label: 'Category' }, { key: 'count', label: 'Invoices', align: 'right' },
                { key: 'total', label: 'Spending', align: 'right', format: money }]} />
            <RankedBarChart title="Time to decide" subtitle="Average time from routing to a reviewer's decision, per review level"
              rows={data.approval_times} valueKey="average_hours" valueName="Average time" format={hours}
              emptyMessage="No reviewer decisions in this period."
              columns={[{ key: 'label', label: 'Review level' }, { key: 'decisions', label: 'Decisions', align: 'right' },
                { key: 'average_hours', label: 'Average', align: 'right', format: hours }]} />
          </div>
        </div>
      )}
    </>
  )
}

function pendingForever() {
  return new Promise(() => {})
}

function Summary({ summary }) {
  return (
    <section aria-label="Headline figures" className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard label="Invoices" value={summary.invoice_count} hint={`${summary.analysed_count} analysed`} icon={FileText} />
      <KpiCard label="Total spending" value={formatCurrency(summary.total_spending)} hint="Drafts and rejected excluded" icon={Banknote} />
      <KpiCard label="Average invoice" value={formatCurrency(summary.average_invoice)} icon={Calculator} />
      <KpiCard label="Alerts raised" value={summary.alert_count} hint={`${summary.open_alert_count} still open`}
        icon={ShieldAlert} tone={summary.open_alert_count ? 'warning' : 'default'} />
      <KpiCard label="Possible duplicates" value={percent(summary.duplicate_rate)} hint="of analysed invoices" icon={Copy} />
      <KpiCard label="High or critical risk" value={percent(summary.high_risk_rate)}
        hint={`of analysed invoices · average score ${summary.average_risk_score}`} icon={TriangleAlert} />
      <KpiCard label="Approved automatically" value={percent(summary.auto_approval_rate)} hint={`of ${summary.decisions} decisions`} icon={Bot} />
      <KpiCard label="Average time to decide" value={hours(summary.average_decision_hours)} hint="Reviewer decisions only" icon={AlarmClock} />
    </section>
  )
}
