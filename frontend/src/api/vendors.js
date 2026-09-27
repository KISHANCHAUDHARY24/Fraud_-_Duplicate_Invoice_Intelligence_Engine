import { api } from './client'
import { cleanParams } from './invoices'

/** Vendors for drop-downs (active and under review can receive invoices). */
export async function vendorOptions() {
  const { data } = await api.get('/vendors/', { params: { page_size: 100, ordering: 'vendor_name' } })
  return data.results
}

export async function listVendors(params) {
  const { data } = await api.get('/vendors/', { params: cleanParams(params) })
  return data
}

export async function getVendor(id) {
  const { data } = await api.get(`/vendors/${id}/`)
  return data
}

/** Totals, risk indicators, monthly spending, recent invoices and bank history in one call. */
export async function vendorDashboard(id) {
  const { data } = await api.get(`/vendors/${id}/dashboard/`)
  return data
}

export async function createVendor(payload) {
  const { data } = await api.post('/vendors/', payload)
  return data
}

export async function updateVendor(id, payload) {
  const { data } = await api.patch(`/vendors/${id}/`, payload)
  return data
}

/** A new account closes the previous one; a change notifies Admins and Auditors. */
export async function addBankAccount(id, payload) {
  const { data } = await api.post(`/vendors/${id}/bank-accounts/`, payload)
  return data
}
