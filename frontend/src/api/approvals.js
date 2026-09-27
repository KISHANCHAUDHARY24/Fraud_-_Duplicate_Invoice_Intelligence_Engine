import { api } from './client'
import { cleanParams } from './invoices'

export async function listApprovals(params) {
  const { data } = await api.get('/approvals/', { params: cleanParams(params) })
  return data
}

/** action: approve | reject | request-clarification | escalate */
export async function decideApproval(id, action, comment) {
  const { data } = await api.post(`/approvals/${id}/${action}/`, { comment })
  return data
}

/** Simulated only: marks an approved invoice as paid. No money is moved. */
export async function simulatePayment(invoiceId) {
  const { data } = await api.post(`/payments/${invoiceId}/simulate/`)
  return data
}
