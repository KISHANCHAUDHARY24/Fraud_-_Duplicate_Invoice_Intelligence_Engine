import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithAuth } from '../test/renderWithAuth'
import NotificationBell from './NotificationBell'

vi.mock('../api/notifications', () => ({
  unreadCount: vi.fn(), latestNotifications: vi.fn(), markRead: vi.fn().mockResolvedValue({}), markAllRead: vi.fn().mockResolvedValue({}),
}))
const api = await import('../api/notifications')

const ITEMS = [
  { id: 1, title: 'Approval needed: INV1001', message: 'High risk', is_read: false, invoice: 12, created_at: '2026-09-24T09:00:00Z' },
  { id: 2, title: 'Invoice approved: EV-2001', message: '', is_read: true, invoice: 9, created_at: '2026-09-23T09:00:00Z' },
]

function Where() {
  return <p data-testid="path">{useLocation().pathname}</p>
}

const renderBell = () => renderWithAuth(<Routes><Route path="*" element={<><NotificationBell /><Where /></>} /></Routes>)

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.unreadCount.mockResolvedValue(1)
    api.latestNotifications.mockResolvedValue(ITEMS)
  })

  it('announces the unread count and opens the latest notifications', async () => {
    renderBell()
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' }))
    expect(await screen.findByText('Approval needed: INV1001')).toBeInTheDocument()
    expect(screen.getByText('Invoice approved: EV-2001')).toBeInTheDocument()
  })

  it('opening an unread notification marks it read and goes to the invoice', async () => {
    renderBell()
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' }))
    await userEvent.click(await screen.findByText('Approval needed: INV1001'))
    expect(api.markRead).toHaveBeenCalledWith(1)
    expect(screen.getByTestId('path')).toHaveTextContent('/invoices/12')
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()   // count is now 0
  })

  it('"Mark all read" clears the count', async () => {
    renderBell()
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' }))
    await userEvent.click(await screen.findByRole('button', { name: /mark all read/i }))
    expect(api.markAllRead).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('says when there is nothing new', async () => {
    api.unreadCount.mockResolvedValue(0)
    api.latestNotifications.mockResolvedValue([])
    renderBell()
    await userEvent.click(await screen.findByRole('button', { name: 'Notifications' }))
    expect(await screen.findByText('You are all caught up.')).toBeInTheDocument()
  })
})
