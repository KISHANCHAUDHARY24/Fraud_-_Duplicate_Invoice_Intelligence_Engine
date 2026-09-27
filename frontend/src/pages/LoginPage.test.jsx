import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import { fakeAuth, renderWithAuth } from '../test/renderWithAuth'
import LoginPage from './LoginPage'

function renderLogin(auth) {
  return renderWithAuth(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<p>Dashboard page</p>} />
    </Routes>,
    { auth, route: '/login' },
  )
}

describe('LoginPage', () => {
  it('shows the message returned by the backend', async () => {
    const login = vi.fn().mockRejectedValue(
      new ApiError({ status: 401, code: 'INVALID_CREDENTIALS', message: 'Invalid username or password.' }),
    )
    renderLogin(fakeAuth({ user: null, login }))
    await userEvent.type(screen.getByLabelText('Username'), 'asha')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password.')
    expect(login).toHaveBeenCalledWith('asha', 'wrong')
  })

  it('validates empty fields without calling the server', async () => {
    const login = vi.fn()
    renderLogin(fakeAuth({ user: null, login }))
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter your username and password.')
    expect(login).not.toHaveBeenCalled()
  })

  it('goes to the dashboard after a successful sign-in', async () => {
    const login = vi.fn().mockResolvedValue({ id: 1 })
    renderLogin(fakeAuth({ user: null, login }))
    await userEvent.type(screen.getByLabelText('Username'), ' asha ')
    await userEvent.type(screen.getByLabelText('Password'), 'Str0ng!Passw0rd')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText('Dashboard page')).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith('asha', 'Str0ng!Passw0rd') // username trimmed
  })

  it('can reveal the password', async () => {
    renderLogin(fakeAuth({ user: null }))
    const password = screen.getByLabelText('Password')
    expect(password).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
  })

  it('explains an expired session', () => {
    renderLogin(fakeAuth({ user: null, sessionMessage: 'Your session has expired. Please sign in again.' }))
    expect(screen.getByRole('status')).toHaveTextContent('Your session has expired')
  })

  it('skips the form for users who are already signed in', () => {
    renderLogin(fakeAuth())
    expect(screen.getByText('Dashboard page')).toBeInTheDocument()
  })
})
