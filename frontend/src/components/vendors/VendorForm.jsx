/**
 * Create or edit a vendor. The first bank account can be added on create; later changes go through
 * the bank-account panel on the vendor page, because every change there raises a review alert.
 */
import { Save } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { fieldErrors } from '../../utils/formErrors'
import { VENDOR_STATUS_OPTIONS } from '../../utils/reviewOptions'
import { validateVendor } from '../../utils/vendorValidation'
import Alert from '../common/Alert'
import Button from '../common/Button'
import { SelectField, TextAreaField } from '../common/Fields'
import FormField from '../common/FormField'

const FIELDS = ['vendor_name', 'registration_number', 'address', 'email', 'phone', 'status', 'bank_name', 'account_number']

export default function VendorForm({ vendor, onSubmit, canChangeStatus = false }) {
  const creating = !vendor
  const [values, setValues] = useState(() => ({
    ...Object.fromEntries(FIELDS.map((field) => [field, vendor?.[field] ?? ''])),
    status: vendor?.status || 'ACTIVE',
  }))
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (field) => (event) => setValues((current) => ({ ...current, [field]: event.target.value }))

  async function save(event) {
    event.preventDefault()
    const clientErrors = validateVendor(values, { creating })
    setErrors(clientErrors)
    setServerError(null)
    if (Object.keys(clientErrors).length) return
    const payload = {
      vendor_name: values.vendor_name.trim(), registration_number: values.registration_number.trim() || null,
      address: values.address.trim(), email: values.email.trim(), phone: values.phone.trim(),
    }
    if (canChangeStatus) payload.status = values.status
    if (creating && values.account_number.trim()) {
      payload.bank_name = values.bank_name.trim()
      payload.account_number = values.account_number.trim()
    }
    setBusy(true)
    try {
      await onSubmit(payload)
    } catch (error) {
      setErrors(fieldErrors(error, FIELDS))
      setServerError(error)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} noValidate className="space-y-5">
      {serverError && (
        <Alert tone="error" title="The vendor could not be saved">
          {serverError.message}
          {serverError.code === 'VENDOR_ALREADY_EXISTS' && serverError.details?.existing_vendor_id && (
            <> <Link to={`/vendors/${serverError.details.existing_vendor_id}`} className="font-medium underline">
              Open the existing vendor</Link></>
          )}
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Vendor name" value={values.vendor_name} onChange={set('vendor_name')} error={errors.vendor_name}
          help="Names like “ACME Corp” and “ACME Corporation” count as the same vendor." className="sm:col-span-2" />
        <FormField label="Registration number" value={values.registration_number} onChange={set('registration_number')}
          error={errors.registration_number} help="Optional. Must be unique." />
        {canChangeStatus ? (
          <SelectField label="Status" value={values.status} onChange={set('status')} options={VENDOR_STATUS_OPTIONS}
            error={errors.status} help="Inactive and blocked vendors cannot receive new invoices." />
        ) : <div className="hidden sm:block" />}
        <FormField label="Email" type="email" value={values.email} onChange={set('email')} error={errors.email} />
        <FormField label="Phone" value={values.phone} onChange={set('phone')} error={errors.phone} />
        <TextAreaField label="Address" value={values.address} onChange={set('address')} error={errors.address}
          rows={2} className="sm:col-span-2" />
      </div>

      {creating && (
        <fieldset className="rounded-lg border border-slate-200 p-4">
          <legend className="px-1 text-sm font-medium text-slate-700">First bank account (optional)</legend>
          <p className="mb-3 text-xs text-slate-500">
            Only the last 4 digits are ever shown again. The full number is stored as a one-way hash, used only to detect changes.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Bank name" value={values.bank_name} onChange={set('bank_name')} error={errors.bank_name} />
            <FormField label="Account number" value={values.account_number} onChange={set('account_number')}
              error={errors.account_number} autoComplete="off" />
          </div>
        </fieldset>
      )}

      <div className="flex justify-end">
        <Button type="submit" icon={Save} loading={busy}>{creating ? 'Create vendor' : 'Save changes'}</Button>
      </div>
    </form>
  )
}
