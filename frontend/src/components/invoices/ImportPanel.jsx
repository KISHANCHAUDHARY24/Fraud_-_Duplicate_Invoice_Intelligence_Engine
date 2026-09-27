/**
 * CSV / JSON bulk import (docs/api.md §2.5): upload -> per-row results -> optionally submit
 * every created invoice for fraud analysis, one after another, with progress.
 */
import { Download, FileUp, Send, UploadCloud } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { downloadCsvTemplate, submitInvoice, uploadCsv, uploadJson } from '../../api/invoices'
import RiskBadge from '../badges/RiskBadge'
import StatusBadge from '../badges/StatusBadge'
import Alert from '../common/Alert'
import Button from '../common/Button'

const ACCEPTED = '.csv,.json'

async function readJson(file) {
  try {
    return JSON.parse(await file.text())
  } catch {
    throw new Error('This file is not valid JSON. Export it again or use the CSV template.')
  }
}

function Summary({ result }) {
  const tone = result.failed === 0 ? 'success' : result.created === 0 ? 'error' : 'warning'
  return (
    <Alert tone={tone} title={`${result.created} of ${result.total_rows} invoices imported`}>
      {result.failed > 0
        ? `${result.failed} row(s) need fixing. Correct them in your file and upload only those rows again.`
        : 'Every row was valid. The invoices are saved as drafts.'}
    </Alert>
  )
}

function RowErrors({ errors }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-sm">
        <caption className="sr-only">Rows that could not be imported</caption>
        <thead className="bg-slate-50 text-left text-xs text-slate-500">
          <tr><th scope="col" className="px-3 py-2 font-medium">Row</th><th scope="col" className="px-3 py-2 font-medium">Field</th>
            <th scope="col" className="px-3 py-2 font-medium">Problem</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {errors.map((error, index) => (
            <tr key={index}>
              <td className="px-3 py-2 text-slate-700 tabular-nums">{error.row}</td>
              <td className="px-3 py-2 font-mono text-xs text-slate-700">{error.field}</td>
              <td className="px-3 py-2 text-slate-700">{error.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SubmissionResults({ results }) {
  return (
    <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
      {results.map((item) => (
        <li key={item.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
          <Link to={`/invoices/${item.id}`} className="font-medium text-brand-700 hover:underline">
            {item.invoice?.invoice_number || `Invoice #${item.id}`}
          </Link>
          {item.error ? <span className="text-red-700">{item.error}</span> : (
            <>
              <RiskBadge level={item.invoice.risk_level} score={item.invoice.risk_score} size="sm" />
              <StatusBadge status={item.invoice.approval_status} />
            </>
          )}
        </li>
      ))}
    </ul>
  )
}

export default function ImportPanel({ canSubmit }) {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [progress, setProgress] = useState(null) // {done, total}
  const [submitted, setSubmitted] = useState(null)

  function choose(selected) {
    if (!selected) return
    setFile(selected)
    setError(null)
    setResult(null)
    setSubmitted(null)
  }

  async function upload() {
    setUploading(true)
    setError(null)
    try {
      const isJson = file.name.toLowerCase().endsWith('.json')
      setResult(isJson ? await uploadJson(await readJson(file)) : await uploadCsv(file))
    } catch (err) {
      setError(err)
    } finally {
      setUploading(false)
    }
  }

  async function submitAll() {
    const ids = result.invoice_ids
    const outcomes = []
    setProgress({ done: 0, total: ids.length })
    for (const id of ids) {
      try {
        outcomes.push({ id, invoice: await submitInvoice(id) })
      } catch (err) {
        outcomes.push({ id, error: err.message })
      }
      setProgress({ done: outcomes.length, total: ids.length })
    }
    setSubmitted(outcomes)
    setProgress(null)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">
          Required columns: <code className="rounded bg-slate-100 px-1 text-xs">invoice_number, vendor, amount, invoice_date, description</code>.
          Dates as YYYY-MM-DD. Up to 1,000 rows and 2 MB.
        </p>
        <Button variant="secondary" size="sm" icon={Download} onClick={() => downloadCsvTemplate().catch(setError)}>
          Download CSV template
        </Button>
      </div>

      <div
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files?.[0]) }}
        className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-slate-50/60'}`}
      >
        <UploadCloud className="size-9 text-slate-400" aria-hidden />
        <p className="mt-3 text-sm text-slate-700">
          Drag a <strong>.csv</strong> or <strong>.json</strong> file here, or{' '}
          <button type="button" onClick={() => inputRef.current?.click()} className="font-medium text-brand-700 underline">
            browse</button>
        </p>
        <input ref={inputRef} type="file" accept={ACCEPTED} className="sr-only" aria-label="Choose an invoice file"
          onChange={(event) => choose(event.target.files?.[0])} />
        {file && <p className="mt-2 text-xs text-slate-500">Selected: <span className="font-medium">{file.name}</span></p>}
      </div>

      <div className="flex justify-end">
        <Button icon={FileUp} disabled={!file} loading={uploading} onClick={upload}>Import invoices</Button>
      </div>

      {error && (
        <Alert tone="error" title="The file could not be imported">
          {error.message}
        </Alert>
      )}

      {result && (
        <div className="space-y-4">
          <Summary result={result} />
          {result.errors.length > 0 && <RowErrors errors={result.errors} />}
          {result.created > 0 && !submitted && canSubmit && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-700">
                Submit the {result.created} imported invoice(s) for fraud analysis now? They are routed to the right reviewer.
              </p>
              <Button icon={Send} loading={Boolean(progress)} onClick={submitAll}>
                {progress ? `Analysing ${progress.done} of ${progress.total}…` : `Submit all ${result.created}`}
              </Button>
            </div>
          )}
          {submitted && <SubmissionResults results={submitted} />}
          <Link to="/invoices?approval_status=DRAFT" className="inline-block text-sm font-medium text-brand-700 hover:underline">
            View drafts in the invoice list
          </Link>
        </div>
      )}
    </div>
  )
}
