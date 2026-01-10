import { useState } from 'react'

/**
 * Status Indicator Component
 *
 * Real-time online/offline badge.
 * Shows last-seen timestamp on hover.
 */
export default function StatusIndicator({ status, lastSeen }) {
  const [showTooltip, setShowTooltip] = useState(false)

  const isOnline = status === 'online'

  const formatLastSeen = (timestamp) => {
    if (!timestamp) return 'Never'

    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className="flex items-center space-x-1">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isOnline ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        <span
          className={`text-xs font-medium ${
            isOnline ? 'text-green-600' : 'text-red-600'
          }`}
        >
          {isOnline ? 'Online' : 'Offline'}
        </span>
      </div>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute top-full left-0 mt-1 px-2 py-1 bg-gray-800 text-white text-xs rounded shadow-lg whitespace-nowrap z-10">
          Last seen: {formatLastSeen(lastSeen)}
        </div>
      )}
    </div>
  )
}
