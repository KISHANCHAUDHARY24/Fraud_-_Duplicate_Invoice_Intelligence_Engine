/**
 * One system setting: a label, the backend's description, an editor suited to the value's shape,
 * and Save / Reset for Admins (read-only for everyone else). Every change is validated by the
 * backend and written to the audit log with the old and new value.
 */
import { RotateCcw, Save } from 'lucide-react'
import { useId, useState } from 'react'

import { resetSetting, updateSetting } from '../../api/settings'
import { formatDateTime } from '../../utils/format'
import { fieldErrors } from '../../utils/formErrors'
import { DAY_NAMES, describeValue, draftProblem, fromDraft, metaFor, orderedEntries, sameValue } from '../../utils/settingsMeta'
import Button from '../common/Button'
import ConfirmDialog from '../common/ConfirmDialog'

const INPUT = 'h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500'

/** Numbers become strings while editing (see fromDraft); arrays (working days) stay as they are. */
function toDraft(value) {
  if (typeof value === 'number') return String(value)
  if (Array.isArray(value) || value === null || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, toDraft(item)]))
}

function initialDraft(meta, value) {
  return meta.editor === 'json' ? JSON.stringify(value, null, 2) : toDraft(value)
}

function NumberInput({ value, onChange, meta, label, disabled, className = 'w-32' }) {
  return (
    <input type="number" inputMode="decimal" value={value} min={meta.min} max={meta.max} step={meta.step ?? 'any'}
      aria-label={label} disabled={disabled} onChange={(event) => onChange(event.target.value)} className={`${INPUT} ${className}`} />
  )
}

function Editor({ meta, draft, setDraft, disabled, labelId }) {
  switch (meta.editor) {
    case 'switch':
      return (
        <label className="inline-flex cursor-pointer items-center gap-3">
          <input type="checkbox" role="switch" checked={Boolean(draft)} disabled={disabled} aria-labelledby={labelId}
            onChange={(event) => setDraft(event.target.checked)} className="peer sr-only" />
          <span aria-hidden className="relative h-6 w-11 rounded-full bg-slate-300 transition-colors peer-checked:bg-brand-700
            peer-focus-visible:ring-2 peer-focus-visible:ring-brand-300 after:absolute after:top-0.5 after:left-0.5 after:size-5
            after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-5" />
          <span className="text-sm text-slate-700">{draft ? 'On' : 'Off'}</span>
        </label>
      )
    case 'number':
      return (
        <div className="flex items-center gap-2">
          <NumberInput value={draft} onChange={setDraft} meta={meta} label={meta.label} disabled={disabled} />
          {meta.unit && <span className="text-sm text-slate-500">{meta.unit}</span>}
        </div>
      )
    case 'text':
      return <input type="text" value={draft} placeholder={meta.placeholder} aria-labelledby={labelId} disabled={disabled}
        onChange={(event) => setDraft(event.target.value)} className={`${INPUT} w-64`} />
    case 'hours':
      return (
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <input type="time" value={draft.start} aria-label="Start time" disabled={disabled} className={INPUT}
            onChange={(event) => setDraft({ ...draft, start: event.target.value })} />
          to
          <input type="time" value={draft.end} aria-label="End time" disabled={disabled} className={INPUT}
            onChange={(event) => setDraft({ ...draft, end: event.target.value })} />
        </div>
      )
    case 'days':
      return (
        <fieldset className="flex flex-wrap gap-2" aria-labelledby={labelId}>
          {DAY_NAMES.map((name, day) => {
            const checked = draft.includes(day)
            return (
              <label key={name} className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-300
                ${checked ? 'border-brand-600 bg-brand-50 font-medium text-brand-800' : 'border-slate-300 text-slate-600'} ${disabled ? 'cursor-default opacity-70' : ''}`}>
                <input type="checkbox" className="sr-only" checked={checked} disabled={disabled}
                  onChange={() => setDraft(checked ? draft.filter((d) => d !== day) : [...draft, day].sort((a, b) => a - b))} />
                {name}
              </label>
            )
          })}
        </fieldset>
      )
    case 'numberMap': {
      const numbers = fromDraft(draft, draft && Object.fromEntries(Object.keys(draft).map((k) => [k, 0])))
      const sum = Object.values(numbers).reduce((total, n) => total + (Number.isNaN(n) ? 0 : n), 0)
      return (
        <div>
          <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">
            {orderedEntries(draft, meta.labels).map(([name, value]) => (
              <label key={name} className="flex items-center justify-between gap-3 text-sm text-slate-700">
                <span>{meta.labels?.[name] || name}</span>
                <NumberInput value={value} meta={meta} label={`${meta.label}: ${meta.labels?.[name] || name}`} disabled={disabled}
                  className="w-24" onChange={(next) => setDraft({ ...draft, [name]: next })} />
              </label>
            ))}
          </div>
          {meta.sumTo !== undefined && (
            <p className={`mt-2 text-xs ${Math.abs(sum - meta.sumTo) > 0.001 ? 'text-red-600' : 'text-slate-500'}`}>
              Total {sum.toFixed(2)} (must be {meta.sumTo})
            </p>
          )}
        </div>
      )
    }
    case 'floors':
      return (
        <table className="text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr><th scope="col" className="py-1 pr-4 font-medium">Signal</th><th scope="col" className="py-1 pr-4 font-medium">From strength (0–1)</th>
              <th scope="col" className="py-1 font-medium">Minimum score</th></tr>
          </thead>
          <tbody>
            {orderedEntries(draft, meta.labels).map(([name, floor]) => {
              const label = meta.labels?.[name] || name
              return (
                <tr key={name}>
                  <td className="py-1 pr-4 text-slate-700">{label}</td>
                  <td className="py-1 pr-4"><NumberInput value={floor.min_strength} meta={{ min: 0, max: 1, step: 0.05 }} className="w-24"
                    label={`${label}: from strength`} disabled={disabled}
                    onChange={(next) => setDraft({ ...draft, [name]: { ...floor, min_strength: next } })} /></td>
                  <td className="py-1"><NumberInput value={floor.min_score} meta={{ min: 0, max: 100, step: 1 }} className="w-24"
                    label={`${label}: minimum score`} disabled={disabled}
                    onChange={(next) => setDraft({ ...draft, [name]: { ...floor, min_score: next } })} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )
    default:
      return <textarea value={typeof draft === 'string' ? draft : JSON.stringify(draft, null, 2)} rows={4} disabled={disabled}
        aria-labelledby={labelId} onChange={(event) => setDraft(event.target.value)} className={`${INPUT} h-auto w-full py-2 font-mono`} />
  }
}

export default function SettingEditor({ setting, canEdit, onSaved }) {
  const meta = metaFor(setting.key)
  const labelId = useId()
  const [draft, setDraft] = useState(() => initialDraft(meta, setting.value))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  const edited = meta.editor === 'json' ? parseJson(draft) : fromDraft(draft, setting.value)
  const dirty = !sameValue(edited, setting.value)
  const isDefault = sameValue(setting.value, setting.default)
  const problem = dirty ? (edited === INVALID_JSON ? 'Not valid JSON.' : draftProblem(setting.key, edited)) : null

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const saved = await updateSetting(setting.key, edited)
      setDraft(initialDraft(meta, saved.value))
      onSaved(saved, 'saved')
    } catch (err) {
      setError(fieldErrors(err, ['value']).value || err.message)
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    const saved = await resetSetting(setting.key)
    setDraft(initialDraft(meta, saved.value))
    setError(null)
    onSaved(saved, 'reset')
  }

  return (
    <div className="grid gap-3 py-5 first:pt-0 last:pb-0 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div>
        <p id={labelId} className="font-medium text-slate-900">{meta.label}</p>
        <p className="mt-0.5 text-sm text-slate-500">{setting.description}</p>
        <p className="mt-1 text-xs text-slate-400">
          Default: {describeValue(setting.key, setting.default)}
          {setting.updated_by_name && ` · changed by ${setting.updated_by_name}, ${formatDateTime(setting.updated_at)}`}
        </p>
      </div>
      <div className="min-w-0">
        <Editor meta={meta} draft={draft} setDraft={setDraft} disabled={!canEdit || busy} labelId={labelId} />
        {(problem || error) && <p role="alert" className="mt-2 text-xs text-red-600">{problem || error}</p>}
        {canEdit && (dirty || !isDefault) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {dirty && <Button size="sm" icon={Save} loading={busy} disabled={Boolean(problem)} onClick={save}>Save</Button>}
            {dirty && <Button size="sm" variant="ghost" disabled={busy}
              onClick={() => { setDraft(initialDraft(meta, setting.value)); setError(null) }}>Cancel</Button>}
            {!dirty && !isDefault && (
              <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => setConfirmReset(true)}>Reset to default</Button>
            )}
          </div>
        )}
      </div>
      <ConfirmDialog open={confirmReset} onClose={() => setConfirmReset(false)} onConfirm={reset}
        title={`Reset “${meta.label}”?`} confirmLabel="Reset to default"
        message={`The value goes back to ${describeValue(setting.key, setting.default)}. New analyses use it immediately; the change is recorded in the audit log.`} />
    </div>
  )
}

const INVALID_JSON = Symbol('invalid-json')

function parseJson(draft) {
  if (typeof draft !== 'string') return draft
  try {
    return JSON.parse(draft)
  } catch {
    return INVALID_JSON
  }
}
