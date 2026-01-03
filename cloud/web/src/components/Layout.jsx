import { useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { useAuth, UserButton } from '@clerk/clerk-react'
import { useQuery } from '@tanstack/react-query'
import {
  Home,
  Camera,
  Settings,
  Users,
  FileVideo,
  Activity,
  Menu,
  X,
  Building2,
  Shield,
} from 'lucide-react'
import { getCurrentUser } from '../api'

export default function Layout() {
  const location = useLocation()
  const { isSignedIn } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const { data: user } = useQuery({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
    enabled: isSignedIn,
  })

  const isAdmin = user?.role === 'admin'

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: Home },
  ]

  const adminNavigation = [
    { name: 'Overview', href: '/admin', icon: Activity },
    { name: 'Sites', href: '/admin/sites', icon: Building2 },
    { name: 'Users', href: '/admin/users', icon: Users },
    { name: 'Exports', href: '/admin/exports', icon: FileVideo },
    { name: 'Audit Log', href: '/admin/audit', icon: Shield },
  ]

  const isActive = (href) => location.pathname === href

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b">
          <Link to="/dashboard" className="flex items-center space-x-2">
            <Camera className="h-8 w-8 text-primary-600" />
            <span className="font-bold text-lg">ZFS</span>
          </Link>
          <button
            className="lg:hidden p-2 rounded-md hover:bg-gray-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="p-4 space-y-1">
          {navigation.map((item) => (
            <Link
              key={item.name}
              to={item.href}
              className={`flex items-center space-x-3 px-3 py-2 rounded-md transition-colors ${
                isActive(item.href)
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.name}</span>
            </Link>
          ))}

          {isAdmin && (
            <>
              <div className="pt-4 pb-2">
                <span className="px-3 text-xs font-semibold text-gray-400 uppercase">
                  Admin
                </span>
              </div>
              {adminNavigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-md transition-colors ${
                    isActive(item.href)
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.name}</span>
                </Link>
              ))}
            </>
          )}
        </nav>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="h-16 bg-white shadow-sm flex items-center justify-between px-4">
          <button
            className="lg:hidden p-2 rounded-md hover:bg-gray-100"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex-1" />

          <div className="flex items-center space-x-4">
            <UserButton afterSignOutUrl="/login" />
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
