import { api } from './client'

/** Drop empty filter values so the URL only carries what the user actually chose. */
export function cleanParams(params) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

export async function listInvoices(params) {
  const { data } = await api.get('/invoices/', { params: cleanParams(params) })
  return data
}

export async function getInvoice(id) {
  const { data } = await api.get(`/invoices/${id}/`)
  return data
}

export async function createInvoice(payload) {
  const { data } = await api.post('/invoices/', payload)
  return data
}

export async function updateInvoice(id, payload) {
  const { data } = await api.patch(`/invoices/${id}/`, payload)
  return data
}

export async function deleteInvoice(id) {
  await api.delete(`/invoices/${id}/`)
}

export async function submitInvoice(id) {
  const { data } = await api.post(`/invoices/${id}/submit/`)
  return data
}

export async function reanalyzeInvoice(id) {
  const { data } = await api.post(`/invoices/${id}/analyze/`)
  return data
}

export async function similarInvoices(id) {
  const { data } = await api.get(`/invoices/${id}/similar/`)
  return data
}

export async function invoiceHistory(id) {
  const { data } = await api.get(`/invoices/${id}/history/`)
  return data
}

export async function uploadCsv(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/invoices/upload-csv/', form)
  return data
}

export async function uploadJson(rows) {
  const { data } = await api.post('/invoices/upload-json/', rows)
  return data
}

/** Download the CSV template (needs the auth header, so a plain link would not work). */
export async function downloadCsvTemplate() {
  const { data } = await api.get('/invoices/csv-template/', { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const link = Object.assign(document.createElement('a'), { href: url, download: 'invoice_import_template.csv' })
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
