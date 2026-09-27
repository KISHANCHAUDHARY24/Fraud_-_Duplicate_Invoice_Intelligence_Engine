import { Bell, CheckCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import * as notificationsApi from '../api/notifications'
import { useDismiss } from '../hooks/useDismiss'
import { timeAgo } from '../utils/format'

const POLL_MS = 60_000

export default function NotificationBell() {
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const close = useCallback(() => setOpen(false), [])
  const ref = useDismiss(open, close)

  const refreshCount = useCallback(() => {
    notificationsApi.unreadCount().then(setUnread).catch(() => {})
  }, [])

  // Poll the unread count every minute and whenever the window regains focus.
  useEffect(() => {
    refreshCount()
    const timer = window.setInterval(refreshCount, POLL_MS)
    window.addEventListener('focus', refreshCount)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', refreshCount)
    }
  }, [refreshCount])

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      setError(null)
      try {
        setItems(await notificationsApi.latestNotifications())
      } catch (err) {
        setError(err)
      }
    }
  }

  async function openNotification(item) {
    if (!item.is_read) {
      notificationsApi.markRead(item.id).catch(() => {})
      setUnread((count) => Math.max(0, count - 1))
    }
    setOpen(false)
    if (item.invoice) navigate(`/invoices/${item.invoice}`)
  }

  async function readAll() {
    await notificationsApi.markAllRead()
    setUnread(0)
    setItems((current) => current?.map((item) => ({ ...item, is_read: true })))
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
      >
        <Bell className="size-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-semibold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-semibold text-slate-900">Notifications</p>
            {unread > 0 && (
              <button type="button" onClick={readAll} className="flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                <CheckCheck className="size-3.5" aria-hidden /> Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {error && <p className="px-4 py-6 text-sm text-red-600">{error.message}</p>}
            {!error && items === null && <p className="px-4 py-6 text-sm text-slate-500">Loading…</p>}
            {!error && items?.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-500">You are all caught up.</p>}
            {items?.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openNotification(item)}
                className={`block w-full border-b border-slate-50 px-4 py-3 text-left hover:bg-slate-50 ${item.is_read ? '' : 'bg-brand-50/60'}`}
              >
                <div className="flex items-start gap-2">
                  {!item.is_read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-brand-600" aria-label="Unread" />}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{item.title}</p>
                    {item.message && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{item.message}</p>}
                    <p className="mt-1 text-[11px] text-slate-400">{item.type_label} · {timeAgo(item.created_at)}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
