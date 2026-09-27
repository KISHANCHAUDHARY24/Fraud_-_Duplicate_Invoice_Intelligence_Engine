import { useId } from 'react'

/** A labelled input with help text and an error message wired up for screen readers. */
export default function FormField({ label, error, help, className = '', inputClassName = '', trailing, ...inputProps }) {
  const id = useId()
  const describedBy = [error && `${id}-error`, help && `${id}-help`].filter(Boolean).join(' ') || undefined
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={`h-10 w-full rounded-lg border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400
            focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none
            ${error ? 'border-red-400' : 'border-slate-300'} ${trailing ? 'pr-10' : ''} ${inputClassName}`}
          {...inputProps}
        />
        {trailing && <div className="absolute inset-y-0 right-0 flex items-center pr-2">{trailing}</div>}
      </div>
      {help && !error && <p id={`${id}-help`} className="mt-1 text-xs text-slate-500">{help}</p>}
      {error && <p id={`${id}-error`} className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
