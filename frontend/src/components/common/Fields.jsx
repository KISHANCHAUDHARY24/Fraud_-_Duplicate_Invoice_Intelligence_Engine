/** Select and text-area fields styled like FormField, with labels and errors wired for screen readers. */
import { useId } from 'react'

const control = (error) => `w-full rounded-lg border bg-white px-3 text-sm text-slate-900
  focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none ${error ? 'border-red-400' : 'border-slate-300'}`

function Frame({ id, label, error, help, className, children }) {
  return (
    <div className={className}>
      {label && <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">{label}</label>}
      {children}
      {help && !error && <p id={`${id}-help`} className="mt-1 text-xs text-slate-500">{help}</p>}
      {error && <p id={`${id}-error`} className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

/** options: [[value, label], ...] */
export function SelectField({ label, error, help, options, placeholder, className = '', ...props }) {
  const id = useId()
  return (
    <Frame id={id} label={label} error={error} help={help} className={className}>
      <select id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined}
        className={`h-10 ${control(error)}`} {...props}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select>
    </Frame>
  )
}

export function TextAreaField({ label, error, help, className = '', rows = 3, ...props }) {
  const id = useId()
  return (
    <Frame id={id} label={label} error={error} help={help} className={className}>
      <textarea id={id} rows={rows} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined}
        className={`py-2 ${control(error)}`} {...props} />
    </Frame>
  )
}
