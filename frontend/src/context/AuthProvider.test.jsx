import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { tokens } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import AuthProvider from './AuthProvider'

vi.mock('../api/auth', () => ({ fetchCurrentUser: vi.fn(), login: vi.fn(), logout: vi.fn() }))
// Keep the real client, but capture the handler the provider registers for "session expired".
vi.mock('../api/client', async (importOriginal) => ({ ...(await importOriginal()), onSessionExpired: vi.fn() }))
const authApi = await import('../api/auth')
const { onSessionExpired } = await import('../api/client')

const ASHA = { id: 1, username: 'asha', first_name: 'Asha', role: 'AP_OFFICER', permissions: ['invoices.view', 'invoices.create'] }

function Probe() {
  const { user, status, sessionMessage, can, login, logout } = useAuth()
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="user">{user?.username ?? 'nobody'}</p>
      <p data-testid="message">{sessionMessage}</p>
      <p data-testid="can">{String(can('invoices.create'))}</p>
      <button type="button" onClick={() => login('asha', 'secret')}>login</button>
      <button type="button" onClick={() => logout()}>logout</button>
    </div>
  )
}

const renderProvider = () => render(<AuthProvider><Probe /></AuthProvider>)
const text = (id) => screen.getByTestId(id).textContent

describe('AuthProvider', () => {
  beforeEach(() => vi.clearAllMocks())

  it('without stored tokens it is ready at once and asks the server nothing', async () => {
    renderProvider()
    expect(await screen.findByText('ready')).toBeInTheDocument()
    expect(text('user')).toBe('nobody')
    expect(authApi.fetchCurrentUser).not.toHaveBeenCalled()
  })

  it('restores the session from stored tokens', async () => {
    tokens.set('access', 'refresh')
    authApi.fetchCurrentUser.mockResolvedValue(ASHA)
    renderProvider()
    expect(await screen.findByText('asha')).toBeInTheDocument()
    expect(text('status')).toBe('ready')
    expect(text('can')).toBe('true')
  })

  it('drops tokens the server no longer accepts', async () => {
    tokens.set('old-access', 'old-refresh')
    authApi.fetchCurrentUser.mockRejectedValue(new Error('401'))
    renderProvider()
    expect(await screen.findByText('ready')).toBeInTheDocument()
    expect(text('user')).toBe('nobody')
    expect([tokens.access, tokens.refresh]).toEqual([null, null])
  })

  it('logs in and out; logging out works even if the server call fails', async () => {
    authApi.login.mockResolvedValue(ASHA)
    authApi.logout.mockRejectedValue(new Error('network'))
    renderProvider()
    await screen.findByText('ready')
    await userEvent.click(screen.getByRole('button', { name: 'login' }))
    expect(authApi.login).toHaveBeenCalledWith('asha', 'secret')
    expect(text('user')).toBe('asha')
    await userEvent.click(screen.getByRole('button', { name: 'logout' }))
    expect(text('user')).toBe('nobody')
    expect(text('can')).toBe('false')
  })

  it('ends the session politely when the refresh token is rejected', async () => {
    tokens.set('access', 'refresh')
    authApi.fetchCurrentUser.mockResolvedValue(ASHA)
    renderProvider()
    await screen.findByText('asha')
    const expire = onSessionExpired.mock.calls.findLast(([handler]) => typeof handler === 'function')[0]
    act(() => expire())                                   // what the API client does when refreshing fails
    expect(text('user')).toBe('nobody')
    expect(text('message')).toBe('Your session has expired. Please sign in again.')
  })

  it('signing out in another tab signs this tab out too', async () => {
    tokens.set('access', 'refresh')
    authApi.fetchCurrentUser.mockResolvedValue(ASHA)
    renderProvider()
    await screen.findByText('asha')
    act(() => {
      tokens.clear()                                      // the other tab removed the shared tokens
      window.dispatchEvent(new StorageEvent('storage', { key: 'ei.access' }))
    })
    expect(text('user')).toBe('nobody')
  })
})
