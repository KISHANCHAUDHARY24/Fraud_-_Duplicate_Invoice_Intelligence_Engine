import {
  Building2, ChartColumn, ClipboardCheck, FileBarChart, FileText, LayoutDashboard, ScrollText, Settings, ShieldAlert,
  Upload,
} from 'lucide-react'

import { Cap } from './permissions'

/**
 * The sidebar, as data. Each item lists the capability needed to see it (any of);
 * `null` means every signed-in user. Routes in App.jsx use the same capabilities.
 */
export const NAVIGATION = [
  {
    group: 'Overview',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, permission: null },
      { to: '/analytics', label: 'Analytics', icon: ChartColumn, permission: Cap.ANALYTICS_VIEW },
    ],
  },
  {
    group: 'Invoices',
    items: [
      { to: '/invoices', label: 'Invoices', icon: FileText, permission: Cap.INVOICES_VIEW, end: true },
      { to: '/invoices/upload', label: 'Upload invoice', icon: Upload, permission: Cap.INVOICES_CREATE },
      { to: '/approvals', label: 'Approvals', icon: ClipboardCheck, permission: Cap.APPROVALS_VIEW },
    ],
  },
  {
    group: 'Risk',
    items: [
      { to: '/fraud-alerts', label: 'Fraud alerts', icon: ShieldAlert, permission: Cap.ALERTS_VIEW },
      { to: '/vendors', label: 'Vendors', icon: Building2, permission: Cap.VENDORS_VIEW },
    ],
  },
  {
    group: 'Governance',
    items: [
      { to: '/audit-logs', label: 'Audit logs', icon: ScrollText, permission: Cap.AUDIT_VIEW },
      { to: '/reports', label: 'Reports', icon: FileBarChart, permission: Cap.REPORTS_EXPORT },
      { to: '/settings', label: 'Settings', icon: Settings, permission: Cap.SETTINGS_VIEW },
    ],
  },
]

/** Navigation filtered to what this user may open (empty groups removed). */
export function navigationFor(can) {
  return NAVIGATION.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.permission === null || can(item.permission)),
  })).filter((section) => section.items.length > 0)
}

/** Title shown in the top bar for the current path. */
export function titleForPath(pathname) {
  if (pathname.startsWith('/profile')) return 'My profile'
  const all = NAVIGATION.flatMap((section) => section.items)
  const exact = all.find((item) => item.to === pathname)
  if (exact) return exact.label
  const parent = all.filter((item) => pathname.startsWith(`${item.to}/`)).sort((a, b) => b.to.length - a.to.length)[0]
  return parent ? parent.label : 'Expense Intelligence'
}
