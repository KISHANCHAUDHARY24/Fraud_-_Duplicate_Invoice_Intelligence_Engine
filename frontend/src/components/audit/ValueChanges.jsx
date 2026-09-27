/** What an audited action changed (AuditLog.old_value / new_value). */

function show(value) {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

/** Old and new values side by side, one line per field; changed values are emphasised. */
export default function ValueChanges({ oldValue, newValue }) {
  const isObject = (value) => value && typeof value === 'object' && !Array.isArray(value)
  if (!oldValue && !newValue) return <p className="text-xs text-slate-500">No values were recorded for this action.</p>
  if (!isObject(oldValue ?? {}) || !isObject(newValue ?? {})) {
    return <p className="text-xs text-slate-600">Before: {show(oldValue)} · After: {show(newValue)}</p>
  }
  const keys = [...new Set([...Object.keys(oldValue || {}), ...Object.keys(newValue || {})])]
  return (
    <table className="w-full max-w-3xl text-xs">
      <thead className="text-left text-slate-500">
        <tr><th scope="col" className="py-1 pr-4 font-medium">Field</th><th scope="col" className="py-1 pr-4 font-medium">Before</th>
          <th scope="col" className="py-1 font-medium">After</th></tr>
      </thead>
      <tbody>
        {keys.map((key) => {
          const before = show(oldValue?.[key])
          const after = show(newValue?.[key])
          return (
            <tr key={key} className="border-t border-slate-100 align-top">
              <td className="py-1 pr-4 font-mono text-slate-600">{key}</td>
              <td className="py-1 pr-4 break-all text-slate-500">{before}</td>
              <td className={`py-1 break-all ${before !== after ? 'font-medium text-slate-900' : 'text-slate-500'}`}>{after}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
