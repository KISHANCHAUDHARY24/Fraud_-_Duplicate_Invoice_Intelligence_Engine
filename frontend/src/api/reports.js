import { api } from './client'
import { cleanParams } from './invoices'

/** The report types this user may export: [{type, title, description, date_basis, formats}]. */
export async function reportTypes() {
  const { data } = await api.get('/reports/')
  return data
}

function filenameFrom(disposition, fallback) {
  const match = /filename="?([^";]+)"?/i.exec(disposition || '')
  return match ? match[1] : fallback
}

/**
 * Download a report. The request needs the auth header, so a plain <a href> would not work:
 * fetch it as a blob, then save it through a temporary object URL.
 * Returns { filename, rows, truncated } from the response headers.
 */
export async function downloadReport(type, { format, date_from, date_to }) {
  const response = await api.get(`/reports/${type}/`, {
    params: cleanParams({ format, date_from, date_to }), responseType: 'blob',
  })
  const filename = filenameFrom(response.headers['content-disposition'], `${type}.${format}`)
  const url = URL.createObjectURL(response.data)
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return {
    filename,
    rows: Number(response.headers['x-report-rows'] ?? 0),
    truncated: response.headers['x-report-truncated'] === 'true',
  }
}
