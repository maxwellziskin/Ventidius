import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Play, Pause, Volume2, VolumeX, Maximize, AlertCircle, Loader2 } from 'lucide-react'

/**
 * HLS Video Player Component
 *
 * Features:
 * - HLS.js-based playback with adaptive bitrate
 * - Play/pause, mute, and fullscreen controls
 * - Connection status indicator
 * - Automatic reconnection on stream interruption
 */
export default function VideoPlayer({ streamUrl, cameraName, onError }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(true)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!streamUrl || !videoRef.current) return

    const video = videoRef.current

    const initPlayer = () => {
      if (Hls.isSupported()) {
        const hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
          liveSyncDuration: 3,
          liveMaxLatencyDuration: 10,
          liveDurationInfinity: true,
          maxBufferLength: 10,
          maxMaxBufferLength: 30,
        })

        hlsRef.current = hls

        hls.loadSource(streamUrl)
        hls.attachMedia(video)

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          setIsLoading(false)
          setError(null)
          setRetryCount(0)
          video.play().catch(() => {})
        })

        hls.on(Hls.Events.ERROR, (event, data) => {
          console.error('HLS error:', data)

          if (data.fatal) {
            switch (data.type) {
              case Hls.ErrorTypes.NETWORK_ERROR:
                setError('Network error - attempting to reconnect...')
                // Retry with exponential backoff
                setTimeout(() => {
                  if (retryCount < 5) {
                    setRetryCount((c) => c + 1)
                    hls.startLoad()
                  } else {
                    setError('Unable to connect to stream')
                    onError?.('Connection failed')
                  }
                }, Math.min(1000 * Math.pow(2, retryCount), 30000))
                break
              case Hls.ErrorTypes.MEDIA_ERROR:
                setError('Media error - recovering...')
                hls.recoverMediaError()
                break
              default:
                setError('Stream unavailable')
                onError?.('Stream error')
                break
            }
          }
        })

      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        // Native HLS support (Safari)
        video.src = streamUrl
        video.addEventListener('loadedmetadata', () => {
          setIsLoading(false)
          setError(null)
          video.play().catch(() => {})
        })
      } else {
        setError('HLS not supported in this browser')
      }
    }

    initPlayer()

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [streamUrl, retryCount])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)

    video.addEventListener('play', handlePlay)
    video.addEventListener('pause', handlePause)

    return () => {
      video.removeEventListener('play', handlePlay)
      video.removeEventListener('pause', handlePause)
    }
  }, [])

  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return

    if (video.paused) {
      video.play()
    } else {
      video.pause()
    }
  }

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return

    video.muted = !video.muted
    setIsMuted(video.muted)
  }

  const toggleFullscreen = () => {
    const video = videoRef.current
    if (!video) return

    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      video.requestFullscreen()
    }
  }

  return (
    <div className="relative bg-black rounded-lg overflow-hidden group">
      {/* Video element */}
      <video
        ref={videoRef}
        className="w-full aspect-video"
        muted={isMuted}
        playsInline
        autoPlay
      />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
          <div className="text-center text-white">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-2" />
            <p>Connecting to stream...</p>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-75">
          <div className="text-center text-white">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* Camera name overlay */}
      {cameraName && (
        <div className="absolute top-2 left-2 px-2 py-1 bg-black bg-opacity-50 rounded text-white text-sm">
          {cameraName}
        </div>
      )}

      {/* Controls overlay */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <button
              onClick={togglePlay}
              className="p-2 rounded-full bg-white bg-opacity-20 hover:bg-opacity-30 text-white"
            >
              {isPlaying ? (
                <Pause className="h-5 w-5" />
              ) : (
                <Play className="h-5 w-5" />
              )}
            </button>

            <button
              onClick={toggleMute}
              className="p-2 rounded-full bg-white bg-opacity-20 hover:bg-opacity-30 text-white"
            >
              {isMuted ? (
                <VolumeX className="h-5 w-5" />
              ) : (
                <Volume2 className="h-5 w-5" />
              )}
            </button>
          </div>

          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-full bg-white bg-opacity-20 hover:bg-opacity-30 text-white"
          >
            <Maximize className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
