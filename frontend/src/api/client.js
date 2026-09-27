/**
 * The one Axios instance every page uses (docs/frontend.md §4).
 *
 *  1. Adds "Authorization: Bearer <access token>" to each request.
 *  2. On 401, refreshes the access token ONCE (concurrent requests wait for the same
 *     refresh) and retries the original request. If refreshing fails, the session ends.
 *  3. Turns every failure into an ApiError {status, code, message, details}, taken from
 *     the backend's {"success": false, "error": {...}} format. Pages show error.message.
 */
import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

// ---------------------------------------------------------------------------
// Token storage. localStorage keeps the user logged in across page reloads.
// Trade-off documented in docs/authentication.md ("Token storage in the browser").
// ---------------------------------------------------------------------------
const ACCESS_KEY = 'ei.access'
const REFRESH_KEY = 'ei.refresh'

function read(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null // storage blocked (private mode, policies): behave as logged out
  }
}

function write(key, value) {
  try {
    if (value) window.localStorage.setItem(key, value)
    else window.localStorage.removeItem(key)
  } catch {
    /* ignore: the session then simply lasts for this page only */
  }
}

export const tokens = {
  get access() {
    return read(ACCESS_KEY)
  },
  get refresh() {
    return read(REFRESH_KEY)
  },
  set(access, refresh) {
    write(ACCESS_KEY, access)
    if (refresh) write(REFRESH_KEY, refresh)
  },
  clear() {
    write(ACCESS_KEY, null)
    write(REFRESH_KEY, null)
  },
  STORAGE_KEYS: [ACCESS_KEY, REFRESH_KEY],
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  constructor({ status = 0, code = 'ERROR', message = 'Something went wrong.', details = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

const FALLBACK_MESSAGES = {
  400: 'The request was not valid.',
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have permission to do that.',
  404: 'Not found.',
  409: 'That action conflicts with the current state.',
  429: 'Too many attempts. Please wait a minute and try again.',
  500: 'The server had a problem. Please try again later.',
  503: 'A service is temporarily unavailable. Please try again later.',
}

export function normalizeError(error) {
  if (error instanceof ApiError) return error
  const response = error?.response
  if (response) {
    const body = response.data?.error
    return new ApiError({
      status: response.status,
      code: body?.code || `HTTP_${response.status}`,
      message: body?.message || FALLBACK_MESSAGES[response.status] || `Request failed (${response.status}).`,
      details: body?.details ?? null,
    })
  }
  if (error?.request) {
    return new ApiError({
      code: 'NETWORK_ERROR',
      message: `Cannot reach the server at ${API_BASE_URL}. Is the Django backend running?`,
    })
  }
  return new ApiError({ code: 'CLIENT_ERROR', message: error?.message || 'Unexpected error.' })
}

// ---------------------------------------------------------------------------
// Axios instance + interceptors
// ---------------------------------------------------------------------------
export const api = axios.create({ baseURL: API_BASE_URL, timeout: 30000 })

let sessionExpiredHandler = null
/** AuthContext registers what to do when the session cannot be renewed (log out). */
export function onSessionExpired(handler) {
  sessionExpiredHandler = handler
}

let refreshInFlight = null

/** File downloads use responseType "blob", so an error body arrives as a Blob: turn JSON back into an object. */
async function readBlobError(error) {
  const data = error?.response?.data
  if (typeof Blob !== 'undefined' && data instanceof Blob && data.type.includes('json')) {
    try {
      error.response.data = JSON.parse(await data.text())
    } catch {
      // not JSON after all: the status-code fallback message is used
    }
  }
}

async function refreshAccessToken() {
  // Plain axios (not `api`) so this call never triggers the interceptor again.
  const { data } = await axios.post(`${API_BASE_URL}/auth/refresh/`, { refresh: tokens.refresh })
  tokens.set(data.access, data.refresh) // rotation: the old refresh token is now blacklisted
  return data.access
}

api.interceptors.request.use((config) => {
  const access = tokens.access
  if (access && !config.skipAuth) {
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    await readBlobError(error)
    const original = error.config
    const canRefresh =
      error.response?.status === 401 && original && !original._retried && !original.skipAuth && tokens.refresh

    if (!canRefresh) return Promise.reject(normalizeError(error))

    original._retried = true
    try {
      // Several requests may fail at once: they all wait for ONE refresh call.
      refreshInFlight ??= refreshAccessToken().finally(() => {
        refreshInFlight = null
      })
      const access = await refreshInFlight
      original.headers.Authorization = `Bearer ${access}`
      return api(original)
    } catch (refreshError) {
      tokens.clear()
      sessionExpiredHandler?.()
      const normalized = normalizeError(refreshError)
      return Promise.reject(
        normalized.status === 401
          ? new ApiError({ status: 401, code: 'SESSION_EXPIRED', message: FALLBACK_MESSAGES[401] })
          : normalized,
      )
    }
  },
)
