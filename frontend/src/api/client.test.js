import axios from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, normalizeError, onSessionExpired, tokens } from './client'

/** A fake HTTP layer: `responses` maps "METHOD url" to a list of [status, body] to return in order. */
function fakeAdapter(responses) {
  const calls = []
  const adapter = async (config) => {
    calls.push({ url: config.url, auth: config.headers.Authorization })
    const [status, data] = responses[config.url].shift()
    const response = { status, data, headers: {}, config, statusText: String(status) }
    if (status >= 400) {
      const error = new Error(`HTTP ${status}`)
      error.config = config
      error.response = response
      throw error
    }
    return response
  }
  return { adapter, calls }
}

describe('normalizeError', () => {
  it('uses the backend error format', () => {
    const error = normalizeError({ response: { status: 409, data: { success: false, error: {
      code: 'DUPLICATE_INVOICE_NUMBER', message: "Invoice number 'INV-1' already exists.", details: { existing_invoice_id: 7 } } } } })
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, code: 'DUPLICATE_INVOICE_NUMBER', details: { existing_invoice_id: 7 } })
    expect(error.message).toBe("Invoice number 'INV-1' already exists.")
  })

  it('falls back to a friendly message when the body is not in our format', () => {
    expect(normalizeError({ response: { status: 500, data: '<html>' } }).message).toMatch(/server had a problem/)
  })

  it('explains network failures', () => {
    const error = normalizeError({ request: {} })
    expect(error.code).toBe('NETWORK_ERROR')
    expect(error.message).toMatch(/Is the Django backend running/)
  })
})

describe('token refresh', () => {
  const original = api.defaults.adapter

  beforeEach(() => tokens.set('old-access', 'refresh-1'))
  afterEach(() => {
    api.defaults.adapter = original
    vi.restoreAllMocks()
    onSessionExpired(null)
  })

  it('refreshes once and retries every request that failed with 401', async () => {
    const { adapter, calls } = fakeAdapter({
      '/a/': [[401, {}], [200, { ok: 'a' }]],
      '/b/': [[401, {}], [200, { ok: 'b' }]],
    })
    api.defaults.adapter = adapter
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { access: 'new-access', refresh: 'refresh-2' } })

    const [a, b] = await Promise.all([api.get('/a/'), api.get('/b/')])

    expect([a.data.ok, b.data.ok]).toEqual(['a', 'b'])
    expect(refresh).toHaveBeenCalledTimes(1)                     // one refresh for both requests
    expect(refresh.mock.calls[0][1]).toEqual({ refresh: 'refresh-1' })
    expect(calls.filter((c) => c.auth === 'Bearer new-access')).toHaveLength(2)
    expect([tokens.access, tokens.refresh]).toEqual(['new-access', 'refresh-2'])   // rotation stored
  })

  it('ends the session when the refresh token is rejected', async () => {
    const { adapter } = fakeAdapter({ '/a/': [[401, {}]] })
    api.defaults.adapter = adapter
    vi.spyOn(axios, 'post').mockRejectedValue({ response: { status: 401, data: {} } })
    const expired = vi.fn()
    onSessionExpired(expired)

    await expect(api.get('/a/')).rejects.toMatchObject({ code: 'SESSION_EXPIRED' })
    expect(expired).toHaveBeenCalled()
    expect(tokens.access).toBeNull()
  })

  it('does not try to refresh a failed login', async () => {
    const { adapter } = fakeAdapter({ '/auth/login/': [[401, { success: false, error: {
      code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' } }]] })
    api.defaults.adapter = adapter
    const refresh = vi.spyOn(axios, 'post')
    await expect(api.post('/auth/login/', {}, { skipAuth: true })).rejects.toMatchObject({ code: 'INVALID_CREDENTIALS' })
    expect(refresh).not.toHaveBeenCalled()
  })

  it('reads the error message of a failed file download (blob response)', async () => {
    const body = { success: false, error: { code: 'PERMISSION_DENIED', message: 'Your role cannot export this report.' } }
    const blob = new Blob([JSON.stringify(body)], { type: 'application/json' })
    const { adapter } = fakeAdapter({ '/reports/audit/': [[403, blob]] })
    api.defaults.adapter = adapter
    await expect(api.get('/reports/audit/', { responseType: 'blob' }))
      .rejects.toMatchObject({ status: 403, message: 'Your role cannot export this report.' })
  })
})
