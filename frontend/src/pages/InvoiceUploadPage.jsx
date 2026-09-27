import { FileSpreadsheet, PenLine } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createInvoice, submitInvoice } from '../api/invoices'
import { vendorOptions } from '../api/vendors'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import ImportPanel from '../components/invoices/ImportPanel'
import InvoiceForm from '../components/invoices/InvoiceForm'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { Cap } from '../utils/permissions'

const TABS = [
  ['manual', 'Enter one invoice', PenLine],
  ['import', 'Import CSV / JSON', FileSpreadsheet],
]

export default function InvoiceUploadPage() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState('manual')
  const { data: vendors, error, reload } = useAsync(vendorOptions)
  const canSubmit = can(Cap.INVOICES_SUBMIT)

  async function save(payload, { andSubmit }) {
    const invoice = await createInvoice(payload)
    if (andSubmit) {
      try {
        await submitInvoice(invoice.id)
      } catch {
        /* the draft exists; the detail page shows it and offers "Submit" again */
      }
    }
    navigate(`/invoices/${invoice.id}`, { state: { justCreated: true, submitted: andSubmit } })
  }

  return (
    <>
      <PageHeader title="Upload invoice"
        description="New invoices are saved as drafts. Submitting runs the fraud analysis and sends the invoice to the right reviewer." />
      <div role="tablist" aria-label="How to add invoices" className="mb-4 inline-flex rounded-lg bg-slate-200/60 p-1">
        {TABS.map(([value, label, Icon]) => (
          <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => setTab(value)}
            className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium ${
              tab === value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}>
            <Icon className="size-4" aria-hidden />{label}
          </button>
        ))}
      </div>
      <Card>
        {tab === 'import' ? (
          <ImportPanel canSubmit={canSubmit} />
        ) : error ? (
          <ErrorState error={error} onRetry={reload} title="Could not load vendors" />
        ) : !vendors ? (
          <LoadingState label="Loading vendors…" />
        ) : (
          <InvoiceForm vendors={vendors} onSubmit={save} submitCapable={canSubmit} />
        )}
      </Card>
    </>
  )
}
