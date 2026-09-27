import { Menu } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { LoadingState } from '../components/common/StateViews'
import { titleForPath } from '../utils/navigation'
import NotificationBell from './NotificationBell'
import Sidebar from './Sidebar'
import UserMenu from './UserMenu'

export default function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const { pathname } = useLocation()
  const title = titleForPath(pathname)

  useEffect(() => {
    document.title = `${title} · Expense Intelligence`
  }, [title])

  return (
    <div className="flex h-full">
      <Sidebar mobileOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button type="button" onClick={() => setMobileNavOpen(true)} aria-label="Open navigation"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden">
            <Menu className="size-5" />
          </button>
          <p className="truncate text-base font-semibold text-slate-800">{title}</p>
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            <NotificationBell />
            <UserMenu />
          </div>
        </header>

        <main className="relative flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
            {/* Pages are loaded on demand (App.jsx): keep the shell visible while one loads. */}
            <Suspense fallback={<LoadingState label="Loading page…" />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}
