import { useState, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  Home,
  Bookmark,
  Lock,
} from 'lucide-react'
import { sendPTZCommand, getPTZPresets } from '../api'

/**
 * PTZ Controls Component
 *
 * Features:
 * - Directional pad (up/down/left/right)
 * - Zoom in/out buttons
 * - Hold to move, release to stop
 * - Preset dropdown for saved positions
 * - Admin lock indicator
 */
export default function PTZControls({ cameraId, canControl = true, onError }) {
  const [activeButton, setActiveButton] = useState(null)
  const [isLocked, setIsLocked] = useState(!canControl)
  const intervalRef = useRef(null)

  const { data: presets = [] } = useQuery({
    queryKey: ['ptzPresets', cameraId],
    queryFn: () => getPTZPresets(cameraId),
    enabled: !!cameraId,
  })

  const sendCommand = useCallback(
    async (action, params = {}) => {
      if (isLocked) return

      try {
        await sendPTZCommand(cameraId, { action, ...params })
      } catch (error) {
        console.error('PTZ command error:', error)
        onError?.(error.message)
      }
    },
    [cameraId, isLocked, onError]
  )

  const startMove = useCallback(
    (direction) => {
      if (isLocked) return

      setActiveButton(direction)

      const params = { pan: 0, tilt: 0, zoom: 0 }
      const speed = 0.5

      switch (direction) {
        case 'up':
          params.tilt = speed
          break
        case 'down':
          params.tilt = -speed
          break
        case 'left':
          params.pan = -speed
          break
        case 'right':
          params.pan = speed
          break
        case 'zoom-in':
          params.zoom = speed
          break
        case 'zoom-out':
          params.zoom = -speed
          break
      }

      sendCommand('move', params)

      // Continue sending while button is held
      intervalRef.current = setInterval(() => {
        sendCommand('move', params)
      }, 100)
    },
    [isLocked, sendCommand]
  )

  const stopMove = useCallback(() => {
    setActiveButton(null)

    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    sendCommand('stop')
  }, [sendCommand])

  const gotoPreset = useCallback(
    (presetId) => {
      sendCommand('preset', { preset_id: presetId })
    },
    [sendCommand]
  )

  const buttonClass = (direction) =>
    `p-3 rounded-lg transition-all ${
      activeButton === direction
        ? 'bg-primary-600 text-white scale-95'
        : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
    } ${isLocked ? 'opacity-50 cursor-not-allowed' : ''}`

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-gray-900">PTZ Control</h3>
        {isLocked && (
          <div className="flex items-center text-sm text-gray-500">
            <Lock className="h-4 w-4 mr-1" />
            Locked
          </div>
        )}
      </div>

      {/* Directional Pad */}
      <div className="grid grid-cols-3 gap-2 mb-4 max-w-[160px] mx-auto">
        <div /> {/* Empty cell */}
        <button
          className={buttonClass('up')}
          onMouseDown={() => startMove('up')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('up')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ArrowUp className="h-5 w-5 mx-auto" />
        </button>
        <div /> {/* Empty cell */}

        <button
          className={buttonClass('left')}
          onMouseDown={() => startMove('left')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('left')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ArrowLeft className="h-5 w-5 mx-auto" />
        </button>

        <button
          className={`${buttonClass('home')} bg-gray-200`}
          onClick={() => gotoPreset(1)}
          disabled={isLocked}
        >
          <Home className="h-5 w-5 mx-auto" />
        </button>

        <button
          className={buttonClass('right')}
          onMouseDown={() => startMove('right')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('right')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ArrowRight className="h-5 w-5 mx-auto" />
        </button>

        <div /> {/* Empty cell */}
        <button
          className={buttonClass('down')}
          onMouseDown={() => startMove('down')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('down')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ArrowDown className="h-5 w-5 mx-auto" />
        </button>
        <div /> {/* Empty cell */}
      </div>

      {/* Zoom Controls */}
      <div className="flex justify-center space-x-4 mb-4">
        <button
          className={`${buttonClass('zoom-out')} px-4`}
          onMouseDown={() => startMove('zoom-out')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('zoom-out')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ZoomOut className="h-5 w-5" />
        </button>
        <button
          className={`${buttonClass('zoom-in')} px-4`}
          onMouseDown={() => startMove('zoom-in')}
          onMouseUp={stopMove}
          onMouseLeave={stopMove}
          onTouchStart={() => startMove('zoom-in')}
          onTouchEnd={stopMove}
          disabled={isLocked}
        >
          <ZoomIn className="h-5 w-5" />
        </button>
      </div>

      {/* Presets */}
      {presets.length > 0 && (
        <div>
          <div className="flex items-center mb-2">
            <Bookmark className="h-4 w-4 text-gray-400 mr-1" />
            <span className="text-sm text-gray-500">Presets</span>
          </div>
          <select
            className="w-full p-2 border rounded-lg text-sm"
            onChange={(e) => e.target.value && gotoPreset(parseInt(e.target.value))}
            disabled={isLocked}
            defaultValue=""
          >
            <option value="">Select preset...</option>
            {presets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}
