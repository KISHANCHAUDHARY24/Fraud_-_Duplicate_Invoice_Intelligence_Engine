import { api } from './client'
import { cleanParams } from './invoices'

/** GET /api/analytics/?date_from=&date_to= (the server defaults to the last 12 months). */
export async function fetchAnalytics(params) {
  const { data } = await api.get('/analytics/', { params: cleanParams(params) })
  return data
}
