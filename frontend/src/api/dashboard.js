import { api } from './client'

export async function fetchDashboardSummary() {
  const { data } = await api.get('/dashboard/summary/')
  return data
}
