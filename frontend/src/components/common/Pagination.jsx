import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ page, pageSize, count, onPage }) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(count, page * pageSize)
  const button = 'inline-flex size-8 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40'
  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm text-slate-600">
      <p>
        {count === 0 ? 'No results' : <>Showing <span className="font-medium text-slate-900">{first}–{last}</span> of{' '}
          <span className="font-medium text-slate-900">{count.toLocaleString()}</span></>}
      </p>
      <div className="flex items-center gap-2">
        <button type="button" className={button} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft className="size-4" />
        </button>
        <span className="tabular-nums">Page {page} of {pages}</span>
        <button type="button" className={button} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight className="size-4" />
        </button>
      </div>
    </nav>
  )
}
