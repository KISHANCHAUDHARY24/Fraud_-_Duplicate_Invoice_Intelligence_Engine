/**
 * A chart panel with a Chart / Table switch. The table view is the accessible alternative
 * (screen readers, colour-blind readers, exact numbers) and is required whenever a
 * palette colour is below 3:1 against the surface.
 */
import { ChartColumn, Table2 } from 'lucide-react'
import { useState } from 'react'

import Card from '../common/Card'
import { EmptyState } from '../common/StateViews'

function ViewToggle({ view, onChange }) {
  const option = (value, Icon, label) => (
    <button
      type="button"
      onClick={() => onChange(value)}
      aria-pressed={view === value}
      aria-label={`Show as ${label}`}
      className={`flex items-center rounded-md px-2 py-1 text-xs font-medium ${
        view === value ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
    >
      <Icon className="size-3.5" aria-hidden />
    </button>
  )
  return (
    <div className="flex rounded-lg bg-slate-100 p-0.5">
      {option('chart', ChartColumn, 'chart')}
      {option('table', Table2, 'table')}
    </div>
  )
}

/** columns: [{ key, label, align?, format? }] */
function DataTable({ columns, rows }) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-white">
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`py-2 pr-3 font-medium ${c.align === 'right' ? 'text-right' : ''}`}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-slate-50">
              {columns.map((c) => (
                <td key={c.key} className={`py-1.5 pr-3 text-slate-700 ${c.align === 'right' ? 'text-right' : ''}`}>
                  {c.format ? c.format(row[c.key], row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** `height` (px) overrides the default 256px plot height, e.g. for ranked bars that grow with the row count. */
export default function ChartCard({ title, subtitle, table, empty, emptyMessage = 'No data for this period yet.', legend, height,
  children }) {
  const [view, setView] = useState('chart')
  return (
    <Card title={title} subtitle={subtitle} actions={<ViewToggle view={view} onChange={setView} />} bodyClassName="px-5 pt-4 pb-5">
      {empty ? (
        <EmptyState title="Nothing to show" message={emptyMessage} />
      ) : view === 'table' ? (
        <DataTable columns={table.columns} rows={table.rows} />
      ) : (
        <>
          {legend}
          <div className={height ? '' : 'h-64'} style={height ? { height } : undefined} role="img" aria-label={`${title} chart. Switch to the table view for exact values.`}>
            {children}
          </div>
        </>
      )}
    </Card>
  )
}
