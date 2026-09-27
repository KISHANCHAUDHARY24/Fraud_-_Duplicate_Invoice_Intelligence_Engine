import { ShieldCheck, X } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'
import { navigationFor } from '../utils/navigation'

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-5 py-5">
      <span className="flex size-9 items-center justify-center rounded-lg bg-white/10">
        <ShieldCheck className="size-5 text-white" aria-hidden />
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-white">Expense Intelligence</p>
        <p className="text-xs text-brand-100/70">Fraud &amp; duplicate detection</p>
      </div>
    </div>
  )
}

function NavigationList({ onNavigate }) {
  const { can } = useAuth()
  return (
    <nav aria-label="Main" className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
      {navigationFor(can).map((section) => (
        <div key={section.group}>
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-brand-100/50">{section.group}</p>
          <ul className="space-y-0.5">
            {section.items.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive ? 'bg-white text-brand-900 shadow-sm' : 'text-brand-100/80 hover:bg-white/10 hover:text-white'
                    }`
                  }
                >
                  <Icon className="size-4.5 shrink-0" aria-hidden />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function Disclaimer() {
  return (
    <p className="border-t border-white/10 px-5 py-4 text-[11px] leading-relaxed text-brand-100/50">
      Risk scores are indicators for human review, not findings of fraud.
    </p>
  )
}

/** Fixed sidebar on large screens; slide-in drawer on small screens. */
export default function Sidebar({ mobileOpen, onClose }) {
  return (
    <>
      <aside className="hidden w-64 shrink-0 flex-col bg-brand-900 lg:flex">
        <Brand />
        <NavigationList />
        <Disclaimer />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} aria-hidden />
          <aside className="relative flex h-full w-72 max-w-[85%] flex-col bg-brand-900 shadow-xl">
            <button type="button" onClick={onClose} aria-label="Close navigation"
              className="absolute top-4 right-3 rounded-md p-1.5 text-brand-100 hover:bg-white/10">
              <X className="size-5" />
            </button>
            <Brand />
            <NavigationList onNavigate={onClose} />
            <Disclaimer />
          </aside>
        </div>
      )}
    </>
  )
}
