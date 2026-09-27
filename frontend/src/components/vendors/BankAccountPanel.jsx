/**
 * Bank account history (masked) and, for Admins, the form to change the account.
 * A change is a classic fraud technique, so it is confirmed first and always raises a review alert.
 */
import { Landmark, RefreshCcw } from 'lucide-react'
import { useState } from 'react'

import { addBankAccount } from '../../api/vendors'
import { formatDate } from '../../utils/format'
import { fieldErrors } from '../../utils/formErrors'
import { ACCOUNT_NUMBER_HELP, isValidAccountNumber } from '../../utils/vendorValidation'
import Button from '../common/Button'
import ConfirmDialog from '../common/ConfirmDialog'
import FormField from '../common/FormField'
import { EmptyState } from '../common/StateViews'

function AccountRow({ account }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3">
      <div>
        <p className="text-sm font-medium text-slate-800">
          {account.bank_name} <span className="font-mono">{account.masked_account}</span>
        </p>
        <p className="text-xs text-slate-500">
          From {formatDate(account.valid_from)}{account.valid_to && ` to ${formatDate(account.valid_to)}`}
          {account.added_by_name && ` · added by ${account.added_by_name}`}
        </p>
      </div>
      {account.is_active
        ? <span className="rounded-md bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">In use</span>
        : <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">Closed</span>}
    </li>
  )
}

export default function BankAccountPanel({ vendorId, accounts, canManage, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState({ bank_name: '', account_number: '' })
  const [errors, setErrors] = useState({})
  const [confirming, setConfirming] = useState(false)
  const hasAccount = accounts.some((account) => account.is_active)
  const set = (field) => (event) => setValues((current) => ({ ...current, [field]: event.target.value }))

  function review(event) {
    event.preventDefault()
    const found = {}
    if (!values.bank_name.trim()) found.bank_name = 'Enter the bank name.'
    if (!isValidAccountNumber(values.account_number)) found.account_number = ACCOUNT_NUMBER_HELP
    setErrors(found)
    if (!Object.keys(found).length) setConfirming(true)
  }

  async function save() {
    try {
      await addBankAccount(vendorId, { bank_name: values.bank_name.trim(), account_number: values.account_number.trim() })
    } catch (error) {
      const found = fieldErrors(error, ['bank_name', 'account_number'])
      if (Object.keys(found).length) {           // show it under the field instead of inside the dialog
        setErrors(found)
        return
      }
      throw error
    }
    setValues({ bank_name: '', account_number: '' })
    setEditing(false)
    onChanged()
  }

  return (
    <>
      {accounts.length === 0 ? (
        <EmptyState icon={Landmark} title="No bank account on file" message="Invoices from this vendor have no payment account yet." />
      ) : (
        <ul className="-my-3 divide-y divide-slate-100">
          {accounts.map((account) => <AccountRow key={account.id} account={account} />)}
        </ul>
      )}

      {canManage && !editing && (
        <Button variant="secondary" size="sm" icon={RefreshCcw} className="mt-4" onClick={() => setEditing(true)}>
          {hasAccount ? 'Change bank account' : 'Add bank account'}
        </Button>
      )}
      {canManage && editing && (
        <form onSubmit={review} noValidate className="mt-4 space-y-3 rounded-lg border border-slate-200 p-4">
          <FormField label="Bank name" value={values.bank_name} onChange={set('bank_name')} error={errors.bank_name} />
          <FormField label="New account number" value={values.account_number} onChange={set('account_number')}
            error={errors.account_number} autoComplete="off" />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => { setEditing(false); setErrors({}) }}>Cancel</Button>
            <Button type="submit" size="sm">Continue</Button>
          </div>
        </form>
      )}

      <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} onConfirm={save} tone="danger"
        title={hasAccount ? 'Change the bank account?' : 'Add a bank account?'}
        confirmLabel={hasAccount ? 'Change account' : 'Add account'}
        message={hasAccount ? (
          <>
            The current account is closed and new invoices will be paid to the new one.
            A bank-account change is a common fraud technique, so <strong>Admins and Auditors are notified</strong>,
            and this vendor&apos;s next invoices get a “Bank account change” risk signal. Confirm the change with the vendor by phone first.
          </>
        ) : 'Invoices from this vendor will be paid to this account.'} />
    </>
  )
}
