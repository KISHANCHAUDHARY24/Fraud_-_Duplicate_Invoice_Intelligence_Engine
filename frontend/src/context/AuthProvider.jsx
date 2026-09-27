/**
 * Who is signed in, what they may do, and how to sign in/out.
 * On page load, a stored token is used to restore the session via GET /api/auth/me/.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'

import * as authApi from '../api/auth'
import { onSessionExpired, tokens } from '../api/client'
import { AuthContext } from './authContext'

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading') // 'loading' until the stored session is checked
  const [sessionMessage, setSessionMessage] = useState('')

  const refreshUser = useCallback(async () => {
    const me = await authApi.fetchCurrentUser()
    setUser(me)
    return me
  }, [])

  // Restore the session once, on first load.
  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (tokens.access || tokens.refresh) {
        try {
          const me = await authApi.fetchCurrentUser()
          if (!cancelled) setUser(me)
        } catch {
          tokens.clear()
        }
      }
      if (!cancelled) setStatus('ready')
    }
    restore()
    return () => {
      cancelled = true
    }
  }, [])

  // If the refresh token is rejected, the API client calls this: end the session politely.
  useEffect(() => {
    onSessionExpired(() => {
      setUser(null)
      setSessionMessage('Your session has expired. Please sign in again.')
    })
    return () => onSessionExpired(null)
  }, [])

  // Logging out in one browser tab logs out the other tabs too.
  useEffect(() => {
    function onStorage(event) {
      if (tokens.STORAGE_KEYS.includes(event.key) && !tokens.access && !tokens.refresh) setUser(null)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const login = useCallback(async (username, password) => {
    const me = await authApi.login(username, password)
    setSessionMessage('')
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      /* the local session is cleared anyway */
    }
    setUser(null)
  }, [])

  const can = useCallback(
    (...permissions) => permissions.some((permission) => user?.permissions?.includes(permission)),
    [user],
  )

  const value = useMemo(
    () => ({ user, status, sessionMessage, login, logout, can, refreshUser, setUser }),
    [user, status, sessionMessage, login, logout, can, refreshUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
