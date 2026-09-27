/**
 * Confirmation for destructive or decisive actions (delete, reject, submit...).
 * With `commentLabel`, a comment is collected; `commentRequired` blocks confirming without one.
 * `children` adds extra fields (e.g. a choice) above the comment; `confirmDisabled` blocks confirming until they are valid.
 * The body mounts only while open, so each opening starts with a fresh, empty state. It is rendered into
 * <body> (a portal), so it never inherits styles from where it was opened, e.g. a table cell.
 */
import { X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import Alert from './Alert'
import Button from './Button'

function DialogBody({
  title, message, confirmLabel, tone, onConfirm, onClose, commentLabel, commentRequired, commentPlaceholder, children,
  confirmDisabled,
}) {
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const titleId = useId()
  const dialogRef = useRef(null)

  useEffect(() => {
    dialogRef.current?.querySelector('select, input, textarea, button[data-confirm]')?.focus()
  }, [])

  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && !busy && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm(comment.trim())
      onClose()
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/50" onClick={() => !busy && onClose()} aria-hidden />
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId}
        className="relative w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <button type="button" onClick={onClose} disabled={busy} aria-label="Close"
          className="absolute top-3 right-3 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <X className="size-4" />
        </button>
        <h2 id={titleId} className="pr-6 text-lg font-semibold text-slate-900">{title}</h2>
        {message && <div className="mt-2 text-sm text-slate-600">{message}</div>}
        {children && <div className="mt-4">{children}</div>}
        {commentLabel && (
          <label className="mt-4 block text-sm font-medium text-slate-700">
            {commentLabel}{commentRequired && <span className="text-red-600"> *</span>}
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={3}
              placeholder={commentPlaceholder}
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none" />
          </label>
        )}
        {error && <Alert tone="error" className="mt-4">{error.message}</Alert>}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button data-confirm variant={tone} loading={busy} onClick={confirm}
            disabled={confirmDisabled || (commentRequired && !comment.trim())}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function ConfirmDialog({ open, confirmLabel = 'Confirm', tone = 'primary', commentRequired = false,
  commentPlaceholder = '', ...props }) {
  if (!open) return null
  return createPortal(
    <DialogBody confirmLabel={confirmLabel} tone={tone} commentRequired={commentRequired}
      commentPlaceholder={commentPlaceholder} {...props} />,
    document.body,
  )
}
