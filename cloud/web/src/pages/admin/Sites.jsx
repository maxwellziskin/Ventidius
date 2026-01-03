import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Building2, MapPin, AlertCircle, MoreVertical, Trash2 } from 'lucide-react'
import StatusIndicator from '../../components/StatusIndicator'
import { getSites, getClients, createSite, deleteSite } from '../../api'

export default function AdminSites() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newSite, setNewSite] = useState({ name: '', client_id: '', address: '' })

  const { data: sites = [], isLoading } = useQuery({
    queryKey: ['sites'],
    queryFn: getSites,
  })

  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: getClients,
  })

  const createMutation = useMutation({
    mutationFn: createSite,
    onSuccess: () => {
      queryClient.invalidateQueries(['sites'])
      setShowCreateModal(false)
      setNewSite({ name: '', client_id: '', address: '' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSite,
    onSuccess: () => {
      queryClient.invalidateQueries(['sites'])
    },
  })

  const handleCreate = (e) => {
    e.preventDefault()
    createMutation.mutate(newSite)
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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sites</h1>
          <p className="text-gray-500">{sites.length} sites configured</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-5 w-5 mr-2" />
          Add Site
        </button>
      </div>

      {/* Sites list */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Site
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Client
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Address
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sites.map((site) => (
              <tr key={site.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <Link
                    to={`/admin/sites/${site.id}`}
                    className="flex items-center hover:text-primary-600"
                  >
                    <Building2 className="h-5 w-5 text-gray-400 mr-3" />
                    <span className="font-medium text-gray-900">{site.name}</span>
                  </Link>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusIndicator status={site.status} lastSeen={site.last_seen} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {clients.find((c) => c.id === site.client_id)?.name || 'Unknown'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <div className="flex items-center">
                    <MapPin className="h-4 w-4 text-gray-400 mr-1" />
                    {site.address || 'No address'}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this site?')) {
                        deleteMutation.mutate(site.id)
                      }
                    }}
                    className="text-red-600 hover:text-red-900"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {sites.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            <Building2 className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p>No sites configured yet</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <form onSubmit={handleCreate}>
              <div className="p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Add New Site</h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Site Name
                    </label>
                    <input
                      type="text"
                      required
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newSite.name}
                      onChange={(e) => setNewSite({ ...newSite, name: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Client
                    </label>
                    <select
                      required
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newSite.client_id}
                      onChange={(e) => setNewSite({ ...newSite, client_id: e.target.value })}
                    >
                      <option value="">Select client...</option>
                      {clients.map((client) => (
                        <option key={client.id} value={client.id}>
                          {client.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Address
                    </label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newSite.address}
                      onChange={(e) => setNewSite({ ...newSite, address: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 bg-gray-50 rounded-b-lg flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Site'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
