import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { fakeAuth, renderWithAuth } from '../../test/renderWithAuth'
import ProtectedRoute from './ProtectedRoute'

function renderRoutes(auth, route = '/secret') {
  return renderWithAuth(
    <Routes>
      <Route path="/login" element={<p>Login page</p>} />
      <Route path="/secret" element={<ProtectedRoute permission="audit.view"><p>Audit logs</p></ProtectedRoute>} />
    </Routes>,
    { auth, route },
  )
}

describe('ProtectedRoute', () => {
  it('sends signed-out users to the login page', () => {
    renderRoutes(fakeAuth({ user: null }))
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Audit logs')).not.toBeInTheDocument()
  })

  it('shows a "no access" page when the role lacks the capability', () => {
    renderRoutes(fakeAuth({ role: 'AP_OFFICER' }))
    expect(screen.getByText('You do not have access to this page')).toBeInTheDocument()
    expect(screen.queryByText('Audit logs')).not.toBeInTheDocument()
  })

  it('renders the page when the role has the capability', () => {
    renderRoutes(fakeAuth({ role: 'ADMIN' }))
    expect(screen.getByText('Audit logs')).toBeInTheDocument()
  })

  it('waits while the stored session is being checked', () => {
    renderRoutes(fakeAuth({ user: null, status: 'loading' }))
    expect(screen.getByRole('status')).toHaveTextContent('Checking your session')
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
  })
})
