import { useQuery } from '@tanstack/react-query'
import { Camera, AlertCircle } from 'lucide-react'
import CameraCard from '../components/CameraCard'
import { getCameras } from '../api'

export default function Dashboard() {
  const { data: cameras = [], isLoading, error } = useQuery({
    queryKey: ['cameras'],
    queryFn: getCameras,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const onlineCameras = cameras.filter((c) => c.status === 'online')
  const offlineCameras = cameras.filter((c) => c.status === 'offline')

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
        <span className="text-red-700">Failed to load cameras: {error.message}</span>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">
          {onlineCameras.length} of {cameras.length} cameras online
        </p>
      </div>

      {cameras.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <Camera className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No cameras</h3>
          <p className="text-gray-500">
            You don't have access to any cameras yet.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {cameras.map((camera) => (
            <CameraCard key={camera.id} camera={camera} />
          ))}
        </div>
      )}

      {/* Offline cameras warning */}
      {offlineCameras.length > 0 && (
        <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-yellow-600 mr-2" />
            <span className="text-yellow-800">
              {offlineCameras.length} camera{offlineCameras.length > 1 ? 's' : ''} offline:{' '}
              {offlineCameras.map((c) => c.name).join(', ')}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
