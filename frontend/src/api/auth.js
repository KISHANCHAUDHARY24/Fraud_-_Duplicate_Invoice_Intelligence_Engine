import { api, tokens } from './client'

export async function login(username, password) {
  const { data } = await api.post('/auth/login/', { username, password }, { skipAuth: true })
  tokens.set(data.access, data.refresh)
  return data.user
}

export async function logout() {
  const refresh = tokens.refresh
  try {
    if (refresh) await api.post('/auth/logout/', { refresh })
  } finally {
    tokens.clear() // always log out locally, even if the server call fails
  }
}

export async function fetchCurrentUser() {
  const { data } = await api.get('/auth/me/')
  return data
}

export async function changePassword(oldPassword, newPassword) {
  const { data } = await api.post('/auth/change-password/', {
    old_password: oldPassword,
    new_password: newPassword,
  })
  tokens.set(data.access, data.refresh) // other devices were logged out; keep this session
  return data
}
