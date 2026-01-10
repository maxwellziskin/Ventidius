import { useQuery } from '@tanstack/react-query'
import { Building2, Camera, Users, Activity, AlertCircle } from 'lucide-react'
import { getStats } from '../../api'

export default function AdminOverview() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
        <span className="text-red-700">Failed to load stats: {error.message}</span>
      </div>
    )
  }

  const statCards = [
    {
      name: 'Clients',
      value: stats?.clients || 0,
      icon: Building2,
      color: 'bg-blue-500',
    },
    {
      name: 'Sites',
      value: `${stats?.sites?.online || 0} / ${stats?.sites?.total || 0}`,
      subtext: 'online',
      icon: Activity,
      color: 'bg-green-500',
    },
    {
      name: 'Cameras',
      value: `${stats?.cameras?.online || 0} / ${stats?.cameras?.total || 0}`,
      subtext: 'online',
      icon: Camera,
      color: 'bg-purple-500',
    },
    {
      name: 'Users',
      value: stats?.users || 0,
      icon: Users,
      color: 'bg-orange-500',
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Admin Overview</h1>
        <p className="text-gray-500">System status and statistics</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat) => (
          <div
            key={stat.name}
            className="bg-white rounded-lg shadow p-6"
          >
            <div className="flex items-center">
              <div className={`${stat.color} p-3 rounded-lg`}>
                <stat.icon className="h-6 w-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm text-gray-500">{stat.name}</p>
                <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                {stat.subtext && (
                  <p className="text-xs text-gray-400">{stat.subtext}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <a
            href="/admin/sites"
            className="block p-4 border rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
          >
            <Building2 className="h-8 w-8 text-primary-600 mb-2" />
            <h3 className="font-medium">Manage Sites</h3>
            <p className="text-sm text-gray-500">Add or configure sites</p>
          </a>
          <a
            href="/admin/users"
            className="block p-4 border rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
          >
            <Users className="h-8 w-8 text-primary-600 mb-2" />
            <h3 className="font-medium">Manage Users</h3>
            <p className="text-sm text-gray-500">Invite and manage users</p>
          </a>
          <a
            href="/admin/exports"
            className="block p-4 border rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
          >
            <Camera className="h-8 w-8 text-primary-600 mb-2" />
            <h3 className="font-medium">Export Clips</h3>
            <p className="text-sm text-gray-500">Request video exports</p>
          </a>
          <a
            href="/admin/audit"
            className="block p-4 border rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
          >
            <Activity className="h-8 w-8 text-primary-600 mb-2" />
            <h3 className="font-medium">Audit Log</h3>
            <p className="text-sm text-gray-500">View system activity</p>
          </a>
        </div>
      </div>
    </div>
  )
}
