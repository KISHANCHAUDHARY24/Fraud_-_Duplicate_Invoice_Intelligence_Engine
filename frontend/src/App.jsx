/**
 * Route table (docs/frontend.md §3). Each protected route names the capability it needs;
 * the same capabilities build the sidebar (utils/navigation.js).
 *
 * Pages behind the login are loaded on demand (React.lazy): the first download only contains the login
 * screen and the app shell, and the chart library arrives with the pages that draw charts.
 * AppLayout shows a loading state (Suspense) while a page's code is fetched.
 */
import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/routing/ProtectedRoute'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import { Cap } from './utils/permissions'

const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))
const ApprovalQueuePage = lazy(() => import('./pages/ApprovalQueuePage'))
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const FraudAlertListPage = lazy(() => import('./pages/FraudAlertListPage'))
const FraudInvestigationPage = lazy(() => import('./pages/FraudInvestigationPage'))
const InvoiceDetailPage = lazy(() => import('./pages/InvoiceDetailPage'))
const InvoiceEditPage = lazy(() => import('./pages/InvoiceEditPage'))
const InvoiceListPage = lazy(() => import('./pages/InvoiceListPage'))
const InvoiceUploadPage = lazy(() => import('./pages/InvoiceUploadPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const VendorDashboardPage = lazy(() => import('./pages/VendorDashboardPage'))
const VendorFormPage = lazy(() => import('./pages/VendorFormPage'))
const VendorListPage = lazy(() => import('./pages/VendorListPage'))

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/invoices" element={<ProtectedRoute permission={Cap.INVOICES_VIEW}><InvoiceListPage /></ProtectedRoute>} />
        <Route path="/invoices/upload" element={<ProtectedRoute permission={Cap.INVOICES_CREATE}><InvoiceUploadPage /></ProtectedRoute>} />
        <Route path="/invoices/:id" element={<ProtectedRoute permission={Cap.INVOICES_VIEW}><InvoiceDetailPage /></ProtectedRoute>} />
        <Route path="/invoices/:id/edit" element={<ProtectedRoute permission={Cap.INVOICES_CREATE}><InvoiceEditPage /></ProtectedRoute>} />
        <Route path="/vendors" element={<ProtectedRoute permission={Cap.VENDORS_VIEW}><VendorListPage /></ProtectedRoute>} />
        <Route path="/vendors/new" element={<ProtectedRoute permission={Cap.VENDORS_CREATE}><VendorFormPage /></ProtectedRoute>} />
        <Route path="/vendors/:id" element={<ProtectedRoute permission={Cap.VENDORS_VIEW}><VendorDashboardPage /></ProtectedRoute>} />
        <Route path="/vendors/:id/edit" element={<ProtectedRoute permission={Cap.VENDORS_EDIT}><VendorFormPage /></ProtectedRoute>} />
        <Route path="/fraud-alerts" element={<ProtectedRoute permission={Cap.ALERTS_VIEW}><FraudAlertListPage /></ProtectedRoute>} />
        <Route path="/fraud-alerts/:id" element={<ProtectedRoute permission={Cap.ALERTS_VIEW}><FraudInvestigationPage /></ProtectedRoute>} />
        <Route path="/approvals" element={<ProtectedRoute permission={Cap.APPROVALS_VIEW}><ApprovalQueuePage /></ProtectedRoute>} />
        <Route path="/analytics" element={<ProtectedRoute permission={Cap.ANALYTICS_VIEW}><AnalyticsPage /></ProtectedRoute>} />
        <Route path="/audit-logs" element={<ProtectedRoute permission={Cap.AUDIT_VIEW}><AuditLogPage /></ProtectedRoute>} />
        <Route path="/reports" element={<ProtectedRoute permission={Cap.REPORTS_EXPORT}><ReportsPage /></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute permission={Cap.SETTINGS_VIEW}><SettingsPage /></ProtectedRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
