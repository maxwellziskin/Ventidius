import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import CameraView from './pages/CameraView'
import AdminOverview from './pages/admin/Overview'
import AdminSites from './pages/admin/Sites'
import AdminSiteDetail from './pages/admin/SiteDetail'
import AdminUsers from './pages/admin/Users'
import AdminExports from './pages/admin/Exports'
import AdminAudit from './pages/admin/Audit'

function ProtectedRoute({ children }) {
  const { isSignedIn, isLoaded } = useAuth()

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!isSignedIn) {
    return <Navigate to="/login" replace />
  }

  return children
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="camera/:id" element={<CameraView />} />

          {/* Admin routes */}
          <Route path="admin" element={<AdminOverview />} />
          <Route path="admin/sites" element={<AdminSites />} />
          <Route path="admin/sites/:id" element={<AdminSiteDetail />} />
          <Route path="admin/users" element={<AdminUsers />} />
          <Route path="admin/exports" element={<AdminExports />} />
          <Route path="admin/audit" element={<AdminAudit />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
