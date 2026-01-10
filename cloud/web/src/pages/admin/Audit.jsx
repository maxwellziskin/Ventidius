import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, User, Camera, Calendar, Filter } from 'lucide-react'
import { getAuditLogs, getUsers, getCameras } from '../../api'

export default function AdminAudit() {
  const [filters, setFilters] = useState({
    user_id: '',
    camera_id: '',
    action: '',
  })

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['auditLogs', filters],
    queryFn: () => getAuditLogs(filters),
  })

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  })

  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: getCameras,
  })

  const actionLabels = {
    stream_view: 'Viewed Stream',
    ptz_move: 'PTZ Move',
    ptz_stop: 'PTZ Stop',
    ptz_preset: 'PTZ Preset',
    export_request: 'Export Requested',
    login: 'Login',
  }

  const getActionBadge = (action) => {
    const colors = {
      stream_view: 'bg-blue-100 text-blue-800',
      ptz_move: 'bg-purple-100 text-purple-800',
      ptz_stop: 'bg-purple-100 text-purple-800',
      ptz_preset: 'bg-purple-100 text-purple-800',
      export_request: 'bg-green-100 text-green-800',
      login: 'bg-gray-100 text-gray-800',
    }

    return (
      <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[action] || 'bg-gray-100 text-gray-800'}`}>
        {actionLabels[action] || action}
      </span>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-gray-500">Track user actions and system events</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center mb-3">
          <Filter className="h-5 w-5 text-gray-400 mr-2" />
          <span className="font-medium text-gray-700">Filters</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-500 mb-1">User</label>
            <select
              className="w-full px-3 py-2 border rounded-lg text-sm"
              value={filters.user_id}
              onChange={(e) => setFilters({ ...filters, user_id: e.target.value })}
            >
              <option value="">All users</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.email}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Camera</label>
            <select
              className="w-full px-3 py-2 border rounded-lg text-sm"
              value={filters.camera_id}
              onChange={(e) => setFilters({ ...filters, camera_id: e.target.value })}
            >
              <option value="">All cameras</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Action</label>
            <select
              className="w-full px-3 py-2 border rounded-lg text-sm"
              value={filters.action}
              onChange={(e) => setFilters({ ...filters, action: e.target.value })}
            >
              <option value="">All actions</option>
              <option value="stream_view">Stream View</option>
              <option value="ptz_move">PTZ Move</option>
              <option value="ptz_stop">PTZ Stop</option>
              <option value="ptz_preset">PTZ Preset</option>
              <option value="export_request">Export Request</option>
            </select>
          </div>
        </div>
      </div>

      {/* Logs table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Timestamp
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Action
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Camera
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                IP Address
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {logs.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <div className="flex items-center">
                    <Calendar className="h-4 w-4 text-gray-400 mr-2" />
                    {new Date(log.timestamp).toLocaleString()}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <User className="h-4 w-4 text-gray-400 mr-2" />
                    <span className="text-sm text-gray-900">
                      {users.find((u) => u.id === log.user_id)?.email || 'Unknown'}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getActionBadge(log.action)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {log.camera_id ? (
                    <div className="flex items-center text-sm text-gray-500">
                      <Camera className="h-4 w-4 text-gray-400 mr-2" />
                      {cameras.find((c) => c.id === log.camera_id)?.name || 'Unknown'}
                    </div>
                  ) : (
                    '-'
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
                  {log.ip_address || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {logs.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            <Activity className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p>No audit logs found</p>
          </div>
        )}
      </div>
    </div>
  )
}
