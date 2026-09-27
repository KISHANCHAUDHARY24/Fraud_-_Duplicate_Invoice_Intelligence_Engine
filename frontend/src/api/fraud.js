import { api } from './client'
import { cleanParams } from './invoices'

export async function listAlerts(params) {
  const { data } = await api.get('/fraud/alerts/', { params: cleanParams(params) })
  return data
}

/** Full investigation payload: alert, invoice + analysis, vendor, similar invoices, histories. */
export async function getInvestigation(id) {
  const { data } = await api.get(`/fraud/alerts/${id}/`)
  return data
}

export async function auditorOptions() {
  const { data } = await api.get('/fraud/alerts/auditors/')
  return data
}

export async function assignAlert(id, auditor) {
  const { data } = await api.post(`/fraud/alerts/${id}/assign/`, { auditor })
  return data
}

export async function markAlertReviewed(id) {
  const { data } = await api.post(`/fraud/alerts/${id}/mark-reviewed/`)
  return data
}

/** outcome: CLEARED | CONFIRMED_ISSUE. The note is required. */
export async function resolveAlert(id, outcome, note) {
  const { data } = await api.post(`/fraud/alerts/${id}/resolve/`, { outcome, note })
  return data
}
