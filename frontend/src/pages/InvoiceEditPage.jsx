import { useCallback } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { getInvoice, updateInvoice } from '../api/invoices'
import { vendorOptions } from '../api/vendors'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import InvoiceForm from '../components/invoices/InvoiceForm'
import { useAsync } from '../hooks/useAsync'

export default function InvoiceEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const loadInvoice = useCallback(() => getInvoice(id), [id])
  const invoice = useAsync(loadInvoice)
  const vendors = useAsync(vendorOptions)

  if (invoice.error || vendors.error) {
    return <Card><ErrorState error={invoice.error || vendors.error} onRetry={invoice.error ? invoice.reload : vendors.reload} /></Card>
  }
  if (!invoice.data || !vendors.data) return <LoadingState label="Loading invoice…" />
  if (!invoice.data.is_editable) return <Navigate to={`/invoices/${id}`} replace />

  async function save(payload) {
    await updateInvoice(id, payload)
    navigate(`/invoices/${id}`)
  }

  return (
    <>
      <PageHeader title={`Edit ${invoice.data.invoice_number}`} description="Only draft invoices can be edited." />
      <Card><InvoiceForm invoice={invoice.data} vendors={vendors.data} onSubmit={save} /></Card>
    </>
  )
}
