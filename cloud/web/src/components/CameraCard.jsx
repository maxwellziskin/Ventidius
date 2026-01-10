import { Link } from 'react-router-dom'
import { Camera } from 'lucide-react'
import StatusIndicator from './StatusIndicator'

/**
 * Camera Card Component
 *
 * Displays camera thumbnail, name, and status.
 * Shows online (green) or offline (red) indicator.
 * Click navigates to camera view.
 */
export default function CameraCard({ camera }) {
  return (
    <Link
      to={`/camera/${camera.id}`}
      className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow overflow-hidden"
    >
      {/* Thumbnail placeholder */}
      <div className="aspect-video bg-gray-800 relative flex items-center justify-center">
        <Camera className="h-12 w-12 text-gray-600" />

        {/* Status indicator */}
        <div className="absolute top-2 right-2">
          <StatusIndicator
            status={camera.status}
            lastSeen={camera.last_seen}
          />
        </div>
      </div>

      {/* Camera info */}
      <div className="p-3">
        <h3 className="font-medium text-gray-900 truncate">{camera.name}</h3>
        <p className="text-sm text-gray-500 truncate">
          {camera.is_ptz ? 'PTZ Camera' : 'Fixed Camera'}
        </p>
      </div>
    </Link>
  )
}
