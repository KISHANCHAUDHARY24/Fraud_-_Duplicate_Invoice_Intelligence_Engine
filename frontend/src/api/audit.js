import { api } from './client'
import { cleanParams } from './invoices'

export async function listAuditLogs(params) {
  const { data } = await api.get('/audit-logs/', { params: cleanParams(params) })
  return data
}

/** [{value, label}] for the action filter. */
export async function auditActions() {
  const { data } = await api.get('/audit-logs/actions/')
  return data
}

/** [{value, label}] record types that appear in the log. */
export async function auditEntityTypes() {
  const { data } = await api.get('/audit-logs/entity-types/')
  return data
}
