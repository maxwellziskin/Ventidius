import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, AlertCircle } from 'lucide-react'
import VideoPlayer from '../components/VideoPlayer'
import PTZControls from '../components/PTZControls'
import StatusIndicator from '../components/StatusIndicator'
import { getCamera, getStreamUrl, getCurrentUser } from '../api'

export default function CameraView() {
  const { id } = useParams()

  const { data: camera, isLoading: cameraLoading } = useQuery({
    queryKey: ['camera', id],
    queryFn: () => getCamera(id),
  })

  const { data: streamData, isLoading: streamLoading, error: streamError } = useQuery({
    queryKey: ['stream', id],
    queryFn: () => getStreamUrl(id),
    enabled: !!camera,
    refetchInterval: 30 * 60 * 1000, // Refresh token every 30 minutes
  })

  const { data: user } = useQuery({
    queryKey: ['currentUser'],
    queryFn: getCurrentUser,
  })

  const isLoading = cameraLoading || streamLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!camera) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
        <span className="text-red-700">Camera not found</span>
      </div>
    )
  }

  // Determine if user can control PTZ
  const canControlPTZ = user?.role === 'admin' || camera.is_ptz

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            to="/dashboard"
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{camera.name}</h1>
            <div className="mt-1">
              <StatusIndicator
                status={camera.status}
                lastSeen={camera.last_seen}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video player */}
        <div className="lg:col-span-2">
          {streamError ? (
            <div className="aspect-video bg-gray-800 rounded-lg flex items-center justify-center">
              <div className="text-center text-white">
                <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
                <p>Unable to load stream</p>
                <p className="text-sm text-gray-400 mt-1">{streamError.message}</p>
              </div>
            </div>
          ) : (
            <VideoPlayer
              streamUrl={streamData?.hls_url}
              cameraName={camera.name}
            />
          )}

          {/* Camera details */}
          <div className="mt-4 bg-white rounded-lg shadow p-4">
            <h3 className="font-medium text-gray-900 mb-3">Camera Details</h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-gray-500">Type</dt>
                <dd className="font-medium">{camera.is_ptz ? 'PTZ Camera' : 'Fixed Camera'}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Status</dt>
                <dd className="font-medium capitalize">{camera.status}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Local IP</dt>
                <dd className="font-medium">{camera.local_ip || 'N/A'}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Last Seen</dt>
                <dd className="font-medium">
                  {camera.last_seen
                    ? new Date(camera.last_seen).toLocaleString()
                    : 'Never'}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        {/* PTZ Controls sidebar */}
        <div className="lg:col-span-1">
          {camera.is_ptz && (
            <PTZControls
              cameraId={id}
              canControl={canControlPTZ}
            />
          )}

          {!camera.is_ptz && (
            <div className="bg-white rounded-lg shadow p-4 text-center text-gray-500">
              <p>This is a fixed camera</p>
              <p className="text-sm mt-1">PTZ controls are not available</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
