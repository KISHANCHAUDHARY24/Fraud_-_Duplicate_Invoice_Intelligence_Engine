/**
 * Investigation actions. Buttons appear only when the role has the capability AND the alert's state
 * allows the step; the backend checks both again (e.g. nobody resolves an alert on their own invoice).
 */
import { CircleCheck, SearchCheck, UserPlus } from 'lucide-react'
import { useCallback, useState } from 'react'

import { assignAlert, auditorOptions, markAlertReviewed, resolveAlert } from '../../api/fraud'
import { useAsync } from '../../hooks/useAsync'
import { useAuth } from '../../hooks/useAuth'
import { Cap } from '../../utils/permissions'
import { OUTCOME_OPTIONS } from '../../utils/reviewOptions'
import Button from '../common/Button'
import ConfirmDialog from '../common/ConfirmDialog'
import { SelectField } from '../common/Fields'

const OUTCOME_HELP = {
  CLEARED: 'The invoice is legitimate. A blocked invoice goes back to an auditor for a normal approval decision.',
  CONFIRMED_ISSUE: 'The invoice is rejected and its payment held. The submitter and the Admins are notified.',
}

function AssignDialog({ alert, onClose, onDone }) {
  const [auditor, setAuditor] = useState(alert.assigned_to ? String(alert.assigned_to) : '')
  const { data: auditors, error } = useAsync(auditorOptions)
  const options = (auditors || []).map((person) => [String(person.id), person.name])
  return (
    <ConfirmDialog open onClose={onClose} title={alert.assigned_to ? 'Reassign this alert' : 'Assign this alert'}
      confirmLabel="Assign" confirmDisabled={!auditor || auditor === String(alert.assigned_to)}
      message="The auditor is notified and the assignment is recorded in the audit log."
      onConfirm={async () => onDone(await assignAlert(alert.id, Number(auditor)))}>
      <SelectField label="Auditor" value={auditor} onChange={(event) => setAuditor(event.target.value)}
        options={options} placeholder={auditors ? 'Choose an auditor…' : 'Loading auditors…'} error={error?.message} />
    </ConfirmDialog>
  )
}

function ResolveDialog({ alert, onClose, onDone }) {
  const [outcome, setOutcome] = useState('')
  return (
    <ConfirmDialog open onClose={onClose} title="Resolve this alert" confirmLabel="Resolve alert"
      tone={outcome === 'CONFIRMED_ISSUE' ? 'danger' : 'primary'} confirmDisabled={!outcome}
      commentLabel="Investigation note" commentRequired
      commentPlaceholder="What did you check, and what did you find? (e.g. called the vendor on the number on file)"
      onConfirm={async (note) => onDone(await resolveAlert(alert.id, outcome, note))}>
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Outcome <span className="text-red-600">*</span></legend>
        <div className="mt-2 space-y-2">
          {OUTCOME_OPTIONS.map(([value, label]) => (
            <label key={value} className={`flex cursor-pointer gap-3 rounded-lg border p-3 text-sm
              ${outcome === value ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:border-slate-300'}`}>
              <input type="radio" name="outcome" value={value} checked={outcome === value}
                onChange={() => setOutcome(value)} className="mt-0.5" />
              <span>
                <span className="font-medium text-slate-800">{label}</span>
                <span className="mt-0.5 block text-xs text-slate-500">{OUTCOME_HELP[value]}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </ConfirmDialog>
  )
}

export default function AlertActions({ alert, invoice, onChanged }) {
  const { user, can } = useAuth()
  const [dialog, setDialog] = useState(null) // 'assign' | 'review' | 'resolve'
  const close = useCallback(() => setDialog(null), [])
  const open = alert.status === 'OPEN' || alert.status === 'IN_REVIEW'
  const ownInvoice = invoice.submitted_by === user.id

  const canAssign = open && can(Cap.ALERTS_ASSIGN)
  const canReview = alert.status === 'OPEN' && can(Cap.ALERTS_RESOLVE)
  const canResolve = open && can(Cap.ALERTS_RESOLVE) && !ownInvoice
  if (!canAssign && !canReview && !canResolve) return null

  return (
    <div className="flex flex-wrap gap-2">
      {canAssign && (
        <Button variant="secondary" icon={UserPlus} onClick={() => setDialog('assign')}>
          {alert.assigned_to ? 'Reassign' : 'Assign'}
        </Button>
      )}
      {canReview && <Button variant="secondary" icon={SearchCheck} onClick={() => setDialog('review')}>Start review</Button>}
      {canResolve && <Button icon={CircleCheck} onClick={() => setDialog('resolve')}>Resolve</Button>}

      {dialog === 'assign' && <AssignDialog alert={alert} onClose={close} onDone={onChanged} />}
      {dialog === 'resolve' && <ResolveDialog alert={alert} onClose={close} onDone={onChanged} />}
      <ConfirmDialog open={dialog === 'review'} onClose={close} title="Start the review?" confirmLabel="Start review"
        message={alert.assigned_to ? 'The alert is marked “In review”.'
          : 'The alert is marked “In review” and assigned to you, so other auditors know you are on it.'}
        onConfirm={async () => onChanged(await markAlertReviewed(alert.id))} />
    </div>
  )
}
