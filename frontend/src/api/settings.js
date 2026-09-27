import { api } from './client'

/** [{key, value, value_type, description, default, updated_by_name, updated_at}] */
export async function listSettings() {
  const { data } = await api.get('/settings/', { params: { page_size: 100 } })
  return Array.isArray(data) ? data : data.results
}

export async function updateSetting(key, value) {
  const { data } = await api.patch(`/settings/${key}/`, { value })
  return data
}

export async function resetSetting(key) {
  const { data } = await api.post(`/settings/${key}/reset/`)
  return data
}
