/**
 * Audit log viewer (Admin, Auditor). Read-only by design: the API has no write endpoints and the
 * table is append-only. Each row opens to show exactly what changed (old → new values).
 */
import { ChevronDown, ChevronRight, ScrollText } from 'lucide-react'
import { Fragment, useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { auditActions, auditEntityTypes, listAuditLogs } from '../api/audit'
import ValueChanges from '../components/audit/ValueChanges'
import Card from '../components/common/Card'
import DateRangeFilter from '../components/common/DateRangeFilter'
import { ClearFilters, FilterSelect, SearchInput } from '../components/common/Filters'
import PageHeader from '../components/common/PageHeader'
import Pagination from '../components/common/Pagination'
import SortHeader from '../components/common/SortHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews'
import { useAsync } from '../hooks/useAsync'
import { paramsFrom, useUrlFilters } from '../hooks/useUrlFilters'
import { rangeError } from '../utils/dateRanges'
import { formatDateTime } from '../utils/format'

const PAGE_SIZE = 25
const FILTER_KEYS = ['search', 'action', 'entity_type', 'date_from', 'date_to']
const DEFAULT_ORDERING = '-timestamp'
const RECORD_LINKS = { invoice: '/invoices', vendor: '/vendors', fraudalert: '/fraud-alerts' }
const noOptions = []

function Record({ entry }) {
  if (!entry.entity_type) return <span className="text-slate-400">—</span>
  const base = RECORD_LINKS[entry.entity_type]
  const text = `${entry.entity_type} #${entry.entity_id}`
  return base ? <Link to={`${base}/${entry.entity_id}`} className="text-brand-700 hover:underline">{text}</Link> : <span>{text}</span>
}

function AuditTable({ entries, ordering, onSort }) {
  const [open, setOpen] = useState(() => new Set())
  const toggle = (id) => setOpen((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50/60 text-xs text-slate-500">
          <tr>
            <th scope="col" className="w-10 px-2"><span className="sr-only">Details</span></th>
            <SortHeader field="timestamp" label="Time" ordering={ordering} onSort={onSort} />
            <SortHeader label="User" />
            <SortHeader field="action" label="Action" ordering={ordering} onSort={onSort} />
            <SortHeader field="entity_type" label="Record" ordering={ordering} onSort={onSort} />
            <SortHeader label="Description" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {entries.map((entry) => {
            const expanded = open.has(entry.id)
            return (
              <Fragment key={entry.id}>
                <tr className="align-top hover:bg-slate-50">
                  <td className="px-2 py-2.5">
                    <button type="button" onClick={() => toggle(entry.id)} aria-expanded={expanded}
                      aria-label={`${expanded ? 'Hide' : 'Show'} details of entry ${entry.id}`}
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                      {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap text-slate-600">{formatDateTime(entry.timestamp)}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap text-slate-700">{entry.user_name}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap font-medium text-slate-800">{entry.action_label}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap"><Record entry={entry} /></td>
                  <td className="min-w-64 px-4 py-2.5 text-slate-600">{entry.description || '—'}</td>
                </tr>
                {expanded && (
                  <tr className="bg-slate-50/70">
                    <td />
                    <td colSpan={5} className="px-4 pt-1 pb-3">
                      <ValueChanges oldValue={entry.old_value} newValue={entry.new_value} />
                      <p className="mt-2 text-xs text-slate-500">
                        Entry #{entry.id}{entry.ip_address && ` · from ${entry.ip_address}`} · {entry.action}
                      </p>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function AuditLogPage() {
  const { values, ordering, page, update, clear, searchText, setSearchText, queryKey } =
    useUrlFilters(FILTER_KEYS, { ordering: DEFAULT_ORDERING })
  const invalid = rangeError(values.date_from, values.date_to)
  const load = useCallback(
    () => listAuditLogs(paramsFrom(queryKey, FILTER_KEYS, { ordering: DEFAULT_ORDERING, pageSize: PAGE_SIZE })),
    [queryKey])
  const { data, error, loading, reload } = useAsync(load)
  const { data: actions } = useAsync(auditActions)
  const { data: entityTypes } = useAsync(auditEntityTypes)
  const filtered = FILTER_KEYS.some((key) => values[key])

  return (
    <>
      <PageHeader title="Audit logs"
        description="Every important action: who did it, what changed and when. Entries cannot be edited or deleted." />
      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-slate-100 p-4 lg:grid-cols-6">
          <SearchInput value={searchText} onChange={setSearchText} placeholder="Description, record id, username…"
            className="lg:col-span-2" />
          <FilterSelect label="Action" value={values.action} onChange={(action) => update({ action })} className="lg:col-span-2"
            options={(actions || noOptions).map((item) => [item.value, item.label])} all="All actions" />
          <FilterSelect label="Record type" value={values.entity_type} onChange={(type) => update({ entity_type: type })}
            options={(entityTypes || noOptions).map((item) => [item.value, item.label])} all="All records" />
          <div className="flex items-end"><ClearFilters visible={filtered} onClear={clear} /></div>
          <DateRangeFilter dateFrom={values.date_from} dateTo={values.date_to} defaultLabel="All time" className="lg:col-span-4"
            onChange={(range) => update(range)} />
        </div>
        {error && !invalid ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <LoadingState label="Loading audit log…" />
        ) : data.count === 0 ? (
          <EmptyState icon={ScrollText} title="No entries match" message="Try another filter or a wider period." />
        ) : (
          <div className={loading ? 'opacity-60 transition-opacity' : ''} aria-busy={loading}>
            <AuditTable entries={data.results} ordering={ordering} onSort={(value) => update({ ordering: value })} />
            <Pagination page={page} pageSize={PAGE_SIZE} count={data.count}
              onPage={(value) => update({ page: value > 1 ? String(value) : '' }, { resetPage: false })} />
          </div>
        )}
      </Card>
    </>
  )
}
