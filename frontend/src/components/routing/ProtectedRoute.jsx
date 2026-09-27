/**
 * Guards a route: signed-out users go to /login (and come back afterwards);
 * signed-in users without the capability see the "not allowed" page.
 * This only shapes the UI; the Django API enforces the same rules on every request.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import ForbiddenPage from '../../pages/ForbiddenPage'
import { FullPageLoader } from '../common/StateViews'

export default function ProtectedRoute({ permission = null, children }) {
  const { user, status, can } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageLoader label="Checking your session…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (permission && !can(...[].concat(permission))) return <ForbiddenPage />
  return children ?? <Outlet />
}
