/**
 * Risk level shown with colour + icon + word (never colour alone, for colour-blind users).
 * The score is optional: <RiskBadge level="HIGH" score={72} /> -> "▲ High · 72"
 * `relative` keeps the screen-reader-only text inside the badge: otherwise it is positioned against <main>
 * and, in a scrolled table, pushes the whole page sideways.
 */
import { CircleCheck, CircleDashed, OctagonAlert, ShieldAlert, TriangleAlert } from 'lucide-react'

const RISK_STYLES = {
  LOW: { label: 'Low', icon: CircleCheck, className: 'bg-risk-low-bg text-risk-low ring-risk-low/20' },
  MEDIUM: { label: 'Medium', icon: TriangleAlert, className: 'bg-risk-medium-bg text-risk-medium ring-risk-medium/20' },
  HIGH: { label: 'High', icon: ShieldAlert, className: 'bg-risk-high-bg text-risk-high ring-risk-high/20' },
  CRITICAL: { label: 'Critical', icon: OctagonAlert, className: 'bg-risk-critical-bg text-risk-critical ring-risk-critical/30' },
}
const NOT_ANALYSED = { label: 'Not analysed', icon: CircleDashed, className: 'bg-slate-100 text-slate-500 ring-slate-300/40' }

export default function RiskBadge({ level, score, size = 'md' }) {
  const style = RISK_STYLES[level] || NOT_ANALYSED
  const Icon = style.icon
  const text = score !== null && score !== undefined && RISK_STYLES[level] ? `${style.label} · ${score}` : style.label
  return (
    <span
      className={`relative inline-flex items-center gap-1 whitespace-nowrap rounded-full font-medium ring-1 ring-inset
        ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'} ${style.className}`}
      title={RISK_STYLES[level] ? `${style.label} risk (risk indicator, not a finding of fraud)` : style.label}
    >
      <Icon className="size-3.5" aria-hidden />
      <span>{text}</span>
      {RISK_STYLES[level] && <span className="sr-only"> risk</span>}
    </span>
  )
}
