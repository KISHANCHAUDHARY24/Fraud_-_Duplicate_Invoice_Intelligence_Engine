/**
 * Create / edit an invoice. Quick checks run in the browser for fast feedback; the Django
 * serializer is the authority, and its field errors are shown under the matching inputs.
 */
import { Save, Send } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fieldErrors } from '../../utils/formErrors'
import { CATEGORY_OPTIONS } from '../../utils/invoiceOptions'
import { validateInvoice } from '../../utils/invoiceValidation'
import Alert from '../common/Alert'
import Button from '../common/Button'
import { SelectField, TextAreaField } from '../common/Fields'
import FormField from '../common/FormField'

const FIELDS = ['vendor', 'invoice_number', 'invoice_date', 'due_date', 'amount', 'currency', 'tax',
  'purchase_category', 'purchase_order_number', 'department', 'description']

function initialValues(invoice) {
  const values = Object.fromEntries(FIELDS.map((field) => [field, invoice?.[field] ?? '']))
  return { ...values, currency: values.currency || 'USD', tax: values.tax || '0.00', purchase_category: values.purchase_category || 'OTHER',
    vendor: values.vendor === '' ? '' : String(values.vendor) }
}

function toPayload(values) {
  return {
    ...values,
    vendor: Number(values.vendor),
    invoice_number: values.invoice_number.trim(),
    currency: values.currency.trim().toUpperCase(),
    due_date: values.due_date || null,
    tax: values.tax === '' ? '0.00' : values.tax,
    description: values.description.trim(),
  }
}

export default function InvoiceForm({ invoice, vendors, onSubmit, submitCapable = false }) {
  const editing = Boolean(invoice)
  const [values, setValues] = useState(() => initialValues(invoice))
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [busy, setBusy] = useState(null) // 'save' | 'submit'

  const set = (field) => (event) => setValues((current) => ({ ...current, [field]: event.target.value }))

  async function save(andSubmit) {
    const clientErrors = validateInvoice(values)
    setErrors(clientErrors)
    setServerError(null)
    if (Object.keys(clientErrors).length) return
    setBusy(andSubmit ? 'submit' : 'save')
    try {
      await onSubmit(toPayload(values), { andSubmit })
    } catch (error) {
      setErrors(fieldErrors(error, FIELDS))
      setServerError(error)
      setBusy(null)
    }
  }

  const vendorOptions = vendors
    .filter((vendor) => ['ACTIVE', 'UNDER_REVIEW'].includes(vendor.status) || String(vendor.id) === values.vendor)
    .map((vendor) => [String(vendor.id), vendor.vendor_name])

  return (
    <form onSubmit={(event) => { event.preventDefault(); save(false) }} noValidate className="space-y-5">
      {serverError && (
        <Alert tone="error" title="The invoice could not be saved">
          {serverError.message}
          {serverError.code === 'DUPLICATE_INVOICE_NUMBER' && serverError.details?.existing_invoice_id && (
            <> <Link to={`/invoices/${serverError.details.existing_invoice_id}`} className="font-medium underline">
              Open the existing invoice</Link></>
          )}
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField label="Vendor" value={values.vendor} onChange={set('vendor')} options={vendorOptions}
          placeholder="Choose a vendor…" error={errors.vendor} className="sm:col-span-2" />
        <FormField label="Invoice number" value={values.invoice_number} onChange={set('invoice_number')}
          error={errors.invoice_number} placeholder="INV-1001" />
        <FormField label="Purchase order number" value={values.purchase_order_number}
          onChange={set('purchase_order_number')} error={errors.purchase_order_number} help="Optional" />
        <FormField label="Invoice date" type="date" value={values.invoice_date} onChange={set('invoice_date')}
          error={errors.invoice_date} />
        <FormField label="Due date" type="date" value={values.due_date || ''} onChange={set('due_date')}
          error={errors.due_date} help="Optional" />
        <FormField label="Amount" type="number" min="0.01" step="0.01" inputMode="decimal" value={values.amount}
          onChange={set('amount')} error={errors.amount} help="Total payable" />
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Currency" value={values.currency} onChange={set('currency')} error={errors.currency} maxLength={3} />
          <FormField label="Tax" type="number" min="0" step="0.01" inputMode="decimal" value={values.tax}
            onChange={set('tax')} error={errors.tax} />
        </div>
        <SelectField label="Category" value={values.purchase_category} onChange={set('purchase_category')}
          options={CATEGORY_OPTIONS} error={errors.purchase_category} />
        <FormField label="Department" value={values.department} onChange={set('department')} error={errors.department}
          help="Defaults to your department" />
        <TextAreaField label="Description" value={values.description} onChange={set('description')}
          error={errors.description} className="sm:col-span-2" placeholder="What was purchased?" />
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
        <Button type="submit" variant={submitCapable && !editing ? 'secondary' : 'primary'} icon={Save}
          loading={busy === 'save'} disabled={Boolean(busy)}>
          {editing ? 'Save changes' : 'Save as draft'}
        </Button>
        {submitCapable && !editing && (
          <Button icon={Send} loading={busy === 'submit'} disabled={Boolean(busy)} onClick={() => save(true)}>
            Save and submit for analysis
          </Button>
        )}
      </div>
    </form>
  )
}
