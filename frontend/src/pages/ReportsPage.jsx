/**
 * Reports: choose a period, then download any report you may export as CSV (Excel) or PDF.
 * The list comes from GET /api/reports/, so each role only sees the reports it can run.
 * Every export is recorded in the audit log.
 */
import { FileSpreadsheet, FileText, FileBarChart } from 'lucide-react'
import { useState } from 'react'

import { downloadReport, reportTypes } from '../api/reports'
import Alert from '../components/common/Alert'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import DateRangeFilter from '../components/common/DateRangeFilter'
import PageHeader from '../components/common/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import { useAsync } from '../hooks/useAsync'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { rangeError } from '../utils/dateRanges'

const FILTER_KEYS = ['date_from', 'date_to']

function ReportCard({ report, range, disabled }) {
  const [busy, setBusy] = useState(null)       // 'csv' | 'pdf'
  const [result, setResult] = useState(null)   // ['success' | 'error', message]

  async function download(format) {
    setBusy(format)
    setResult(null)
    try {
      const { filename, rows, truncated } = await downloadReport(report.type, { format, ...range })
      setResult(['success', truncated
        ? `${filename}: the first ${rows} rows. The PDF is limited; export CSV for everything.`
        : `${filename} downloaded (${rows} row${rows === 1 ? '' : 's'}).`])
    } catch (error) {
      setResult(['error', error.message])
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="flex flex-col" bodyClassName="flex flex-1 flex-col p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
          <FileBarChart className="size-5" aria-hidden />
        </span>
        <div>
          <h2 className="font-semibold text-slate-900">{report.title}</h2>
          <p className="mt-0.5 text-sm text-slate-600">{report.description}</p>
          <p className="mt-1 text-xs text-slate-500">The period filters on the {report.date_basis}.</p>
        </div>
      </div>
      <div className="mt-auto flex flex-wrap gap-2 pt-4">
        <Button variant="secondary" size="sm" icon={FileSpreadsheet} loading={busy === 'csv'} disabled={disabled || Boolean(busy)}
          onClick={() => download('csv')} aria-label={`Download ${report.title} as CSV`}>CSV</Button>
        <Button variant="secondary" size="sm" icon={FileText} loading={busy === 'pdf'} disabled={disabled || Boolean(busy)}
          onClick={() => download('pdf')} aria-label={`Download ${report.title} as PDF`}>PDF</Button>
      </div>
      {result && <Alert tone={result[0]} className="mt-3">{result[1]}</Alert>}
    </Card>
  )
}

export default function ReportsPage() {
  const { values, update } = useUrlFilters(FILTER_KEYS)
  const { data: reports, error, reload } = useAsync(reportTypes)
  const invalid = rangeError(values.date_from, values.date_to)

  return (
    <>
      <PageHeader title="Reports"
        description="Download invoice, fraud, vendor, approval and audit reports for a period. CSV opens in Excel; PDF is for printing and sharing." />
      <Card className="mb-6">
        <DateRangeFilter dateFrom={values.date_from} dateTo={values.date_to} onChange={(range) => update(range)} />
        <p className="mt-3 text-xs text-slate-500">
          Reports contain only data your role may see. Bank accounts are always masked. Each download is recorded in the audit log.
        </p>
      </Card>
      {error ? (
        <Card><ErrorState error={error} onRetry={reload} /></Card>
      ) : !reports ? (
        <LoadingState label="Loading reports…" />
      ) : reports.length === 0 ? (
        <Card><EmptyState title="No reports available" message="Your role cannot export reports." /></Card>
      ) : (
        <div className="grid gap-4 [&>*]:min-w-0 md:grid-cols-2 xl:grid-cols-3">
          {reports.map((report) => (
            <ReportCard key={report.type} report={report} disabled={Boolean(invalid)}
              range={{ date_from: values.date_from, date_to: values.date_to }} />
          ))}
        </div>
      )}
    </>
  )
}
