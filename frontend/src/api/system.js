import { api } from './client'

/** GET /api/health/: database + ML service status (public endpoint). */
export async function fetchHealth() {
  try {
    const { data } = await api.get('/health/', { skipAuth: true })
    return data
  } catch (error) {
    // A 503 still carries a useful body (database down); anything else means Django is down.
    return error.status === 503 ? { status: 'degraded', database: 'unavailable' } : null
  }
}
