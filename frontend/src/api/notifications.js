import { api } from './client'

export async function unreadCount() {
  const { data } = await api.get('/notifications/unread-count/')
  return data.unread
}

export async function latestNotifications(limit = 8) {
  const { data } = await api.get('/notifications/', { params: { page_size: limit } })
  return data.results
}

export async function markRead(id) {
  const { data } = await api.post(`/notifications/${id}/read/`)
  return data
}

export async function markAllRead() {
  const { data } = await api.post('/notifications/read-all/')
  return data
}
