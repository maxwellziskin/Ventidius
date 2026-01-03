import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Camera,
  Plus,
  RefreshCw,
  Trash2,
  Key,
  AlertCircle,
} from 'lucide-react'
import StatusIndicator from '../../components/StatusIndicator'
import { getSite, getSiteCameras, getSiteHealth, rebootSite } from '../../api'

export default function AdminSiteDetail() {
  const { id } = useParams()
  const queryClient = useQueryClient()

  const { data: site, isLoading: siteLoading } = useQuery({
    queryKey: ['site', id],
    queryFn: () => getSite(id),
  })

  const { data: cameras = [] } = useQuery({
    queryKey: ['siteCameras', id],
    queryFn: () => getSiteCameras(id),
  })

  const { data: health } = useQuery({
    queryKey: ['siteHealth', id],
    queryFn: () => getSiteHealth(id),
    refetchInterval: 30000,
  })

  const rebootMutation = useMutation({
    mutationFn: () => rebootSite(id),
    onSuccess: () => {
      alert('Reboot command sent')
    },
  })

  if (siteLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!site) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
        <span className="text-red-700">Site not found</span>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            to="/admin/sites"
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{site.name}</h1>
            <div className="mt-1">
              <StatusIndicator status={site.status} lastSeen={site.last_seen} />
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => rebootMutation.mutate()}
            disabled={rebootMutation.isPending || site.status !== 'online'}
            className="flex items-center px-4 py-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-5 w-5 mr-2 ${rebootMutation.isPending ? 'animate-spin' : ''}`} />
            Reboot
          </button>
        </div>
      </div>

      {/* Site info */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Site Information</h2>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-gray-500">Address</dt>
              <dd className="font-medium">{site.address || 'Not specified'}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">WireGuard IP</dt>
              <dd className="font-medium font-mono">{site.wireguard_ip || 'Not configured'}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">Created</dt>
              <dd className="font-medium">
                {new Date(site.created_at).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">Last Seen</dt>
              <dd className="font-medium">
                {site.last_seen ? new Date(site.last_seen).toLocaleString() : 'Never'}
              </dd>
            </div>
          </dl>

          {site.api_key && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Key className="h-5 w-5 text-gray-400 mr-2" />
                  <span className="text-sm text-gray-600">API Key</span>
                </div>
                <code className="text-sm font-mono bg-white px-2 py-1 rounded border">
                  {site.api_key.substring(0, 20)}...
                </code>
              </div>
            </div>
          )}
        </div>

        {/* System health */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">System Health</h2>
          {health ? (
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">CPU</span>
                  <span className="font-medium">{health.system?.cpu?.percent || 0}%</span>
                </div>
                <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: `${health.system?.cpu?.percent || 0}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Memory</span>
                  <span className="font-medium">{health.system?.memory?.percent || 0}%</span>
                </div>
                <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: `${health.system?.memory?.percent || 0}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Disk</span>
                  <span className="font-medium">{health.system?.disk?.percent || 0}%</span>
                </div>
                <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: `${health.system?.disk?.percent || 0}%` }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No health data available</p>
          )}
        </div>
      </div>

      {/* Cameras */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-900">Cameras</h2>
          <button className="flex items-center px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            <Plus className="h-4 w-4 mr-1" />
            Add Camera
          </button>
        </div>

        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Camera
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                IP Address
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {cameras.map((camera) => (
              <tr key={camera.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <Camera className="h-5 w-5 text-gray-400 mr-3" />
                    <span className="font-medium">{camera.name}</span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusIndicator status={camera.status} lastSeen={camera.last_seen} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {camera.is_ptz ? 'PTZ' : 'Fixed'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
                  {camera.local_ip || 'N/A'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  <Link
                    to={`/camera/${camera.id}`}
                    className="text-primary-600 hover:text-primary-900 text-sm font-medium"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {cameras.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            <Camera className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p>No cameras configured for this site</p>
          </div>
        )}
      </div>
    </div>
  )
}
