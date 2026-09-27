/** A table header that sorts by its column. Without `onSort` it renders a plain header. */
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'

// Full class names (Tailwind only generates classes it can find written out in the source).
const ALIGN = { left: 'text-left', right: 'text-right' }

/** ordering: e.g. "-risk_score". Clicking a header toggles ascending / descending. */
export default function SortHeader({ field, label, ordering, onSort, align = 'left' }) {
  if (!onSort) return <th scope="col" className={`px-4 py-3 font-medium ${ALIGN[align]}`}>{label}</th>
  const active = ordering?.replace('-', '') === field
  const descending = ordering?.startsWith('-')
  const Icon = !active ? ArrowUpDown : descending ? ArrowDown : ArrowUp
  const next = active && !descending ? `-${field}` : field
  return (
    <th scope="col" className={`px-4 py-3 font-medium ${ALIGN[align]}`}
      aria-sort={active ? (descending ? 'descending' : 'ascending') : 'none'}>
      <button type="button" onClick={() => onSort(next)}
        className={`inline-flex items-center gap-1 hover:text-slate-900 ${active ? 'text-slate-900' : ''}`}>
        {label}
        <Icon className="size-3.5" aria-hidden />
      </button>
    </th>
  )
}
