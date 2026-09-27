/** The loading / empty / error states every data view must show (docs/frontend.md §5). */
import { CircleAlert, Inbox, LoaderCircle, RefreshCw } from 'lucide-react'

import Button from './Button'

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-3 py-12 text-slate-500 ${className}`}>
      <LoaderCircle className="size-5 animate-spin" aria-hidden />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function FullPageLoader({ label = 'Loading…' }) {
  return (
    <div className="flex h-full items-center justify-center">
      <LoadingState label={label} />
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', message, action, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <Icon className="size-10 text-slate-300" aria-hidden />
      <p className="mt-3 font-medium text-slate-700">{title}</p>
      {message && <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry, title = 'Could not load this data' }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <CircleAlert className="size-10 text-red-400" aria-hidden />
      <p className="mt-3 font-medium text-slate-800">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{error?.message || 'Something went wrong.'}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" icon={RefreshCw} className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
