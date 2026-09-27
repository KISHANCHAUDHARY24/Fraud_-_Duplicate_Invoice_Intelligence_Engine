/** Hover tooltip shared by all charts: text in ink colours, identity from a small swatch. */
export default function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter = (v) => v }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      {label !== undefined && <p className="mb-1 font-medium text-slate-800">{labelFormatter ? labelFormatter(label) : label}</p>}
      <ul className="space-y-0.5">
        {payload.map((item) => (
          <li key={item.dataKey} className="flex items-center gap-2 text-slate-600">
            <span className="size-2.5 rounded-sm" style={{ background: item.color || item.payload?.fill }} aria-hidden />
            <span>{item.name}</span>
            <span className="ml-auto pl-3 font-medium text-slate-900 tabular-nums">{valueFormatter(item.value, item)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
