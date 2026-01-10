import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileVideo, Download, Clock, Check, X, AlertCircle, Loader2 } from 'lucide-react'
import { getExports, getCameras, createExport, cancelExport } from '../../api'

export default function AdminExports() {
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newExport, setNewExport] = useState({
    camera_id: '',
    start_time: '',
    end_time: '',
  })

  const { data: exports = [], isLoading } = useQuery({
    queryKey: ['exports'],
    queryFn: () => getExports(),
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: cameras = [] } = useQuery({
    queryKey: ['cameras'],
    queryFn: getCameras,
  })

  const createMutation = useMutation({
    mutationFn: createExport,
    onSuccess: () => {
      queryClient.invalidateQueries(['exports'])
      setShowCreateModal(false)
      setNewExport({ camera_id: '', start_time: '', end_time: '' })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: cancelExport,
    onSuccess: () => {
      queryClient.invalidateQueries(['exports'])
    },
  })

  const handleCreate = (e) => {
    e.preventDefault()
    createMutation.mutate({
      camera_id: newExport.camera_id,
      start_time: new Date(newExport.start_time).toISOString(),
      end_time: new Date(newExport.end_time).toISOString(),
    })
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-5 w-5 text-yellow-500" />
      case 'processing':
      case 'uploading':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
      case 'completed':
        return <Check className="h-5 w-5 text-green-500" />
      case 'failed':
        return <X className="h-5 w-5 text-red-500" />
      default:
        return null
    }
  }

  const getStatusBadge = (status) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      processing: 'bg-blue-100 text-blue-800',
      uploading: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    }

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {getStatusIcon(status)}
        <span className="ml-1 capitalize">{status}</span>
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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Video Exports</h1>
          <p className="text-gray-500">{exports.length} export requests</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <FileVideo className="h-5 w-5 mr-2" />
          Request Export
        </button>
      </div>

      {/* Exports list */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Camera
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Time Range
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Size
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {exports.map((exp) => (
              <tr key={exp.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="font-medium">
                    {cameras.find((c) => c.id === exp.camera_id)?.name || 'Unknown'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <div>{new Date(exp.start_time).toLocaleString()}</div>
                  <div className="text-gray-400">to {new Date(exp.end_time).toLocaleString()}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(exp.status)}
                  {exp.error_message && (
                    <p className="text-xs text-red-500 mt-1">{exp.error_message}</p>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {exp.file_size
                    ? `${(exp.file_size / 1024 / 1024).toFixed(1)} MB`
                    : '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  {exp.status === 'completed' && exp.file_url && (
                    <a
                      href={exp.file_url}
                      className="inline-flex items-center text-primary-600 hover:text-primary-900"
                    >
                      <Download className="h-5 w-5" />
                    </a>
                  )}
                  {['pending', 'processing'].includes(exp.status) && (
                    <button
                      onClick={() => cancelMutation.mutate(exp.id)}
                      className="text-red-600 hover:text-red-900"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {exports.length === 0 && (
          <div className="p-8 text-center text-gray-500">
            <FileVideo className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p>No export requests yet</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <form onSubmit={handleCreate}>
              <div className="p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Request Video Export</h2>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Camera
                    </label>
                    <select
                      required
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newExport.camera_id}
                      onChange={(e) => setNewExport({ ...newExport, camera_id: e.target.value })}
                    >
                      <option value="">Select camera...</option>
                      {cameras.map((camera) => (
                        <option key={camera.id} value={camera.id}>
                          {camera.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Start Time
                    </label>
                    <input
                      type="datetime-local"
                      required
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newExport.start_time}
                      onChange={(e) => setNewExport({ ...newExport, start_time: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      End Time
                    </label>
                    <input
                      type="datetime-local"
                      required
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500"
                      value={newExport.end_time}
                      onChange={(e) => setNewExport({ ...newExport, end_time: e.target.value })}
                    />
                  </div>

                  <p className="text-sm text-gray-500">
                    Maximum export duration is 4 hours.
                  </p>
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
                  {createMutation.isPending ? 'Creating...' : 'Request Export'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
