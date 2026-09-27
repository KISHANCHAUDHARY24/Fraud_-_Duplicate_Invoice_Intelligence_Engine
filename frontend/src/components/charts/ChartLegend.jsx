/** Legend for multi-series charts: a colour swatch beside a text label (identity is never colour alone). */
export default function ChartLegend({ items }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {items.map(([label, color]) => (
        <li key={label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: color }} aria-hidden />
          {label}
        </li>
      ))}
    </ul>
  )
}
