"""
Ziskin Field Systems - Stream Manager Module

Manages MediaMTX for RTSP ingestion and HLS output.
"""

import asyncio
import subprocess
import signal
import structlog
from pathlib import Path
from typing import Optional
import yaml

from config import MediaMTXConfig, CameraConfig

logger = structlog.get_logger(__name__)


class StreamManager:
    """Manages MediaMTX streaming server."""

    def __init__(self, config: MediaMTXConfig, cameras: list[CameraConfig]):
        self.config = config
        self.cameras = cameras
        self.process: Optional[subprocess.Popen] = None
        self.running = False

    async def start(self):
        """Start the MediaMTX streaming server."""
        logger.info("Starting MediaMTX stream server")

        # Generate MediaMTX configuration
        await self._generate_config()

        # Start MediaMTX process
        try:
            self.process = subprocess.Popen(
                ["mediamtx", self.config.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
            )
            self.running = True

            # Give MediaMTX time to start
            await asyncio.sleep(2)

            if self.process.poll() is not None:
                # Process already exited
                stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                raise RuntimeError(f"MediaMTX failed to start: {stderr}")

            logger.info(
                "MediaMTX started successfully",
                pid=self.process.pid,
                rtsp_port=self.config.rtsp_port,
                hls_port=self.config.hls_port
            )

        except FileNotFoundError:
            logger.error("MediaMTX binary not found")
            raise
        except Exception as e:
            logger.error("Failed to start MediaMTX", error=str(e))
            raise

    async def stop(self):
        """Stop the MediaMTX streaming server."""
        if self.process and self.running:
            logger.info("Stopping MediaMTX")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("MediaMTX did not stop gracefully, killing")
                self.process.kill()
            self.running = False
            logger.info("MediaMTX stopped")

    async def _generate_config(self):
        """Generate MediaMTX configuration file."""
        config_path = Path(self.config.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Build paths configuration for each camera
        paths = {}
        for camera in self.cameras:
            # Main stream path
            paths[f"{camera.id}-main"] = {
                "source": camera.rtsp_main_url,
                "sourceProtocol": "tcp",
                "sourceOnDemand": False,
            }
            # Sub stream path (for HLS streaming)
            paths[f"{camera.id}"] = {
                "source": camera.rtsp_sub_url,
                "sourceProtocol": "tcp",
                "sourceOnDemand": True,
                "sourceOnDemandStartTimeout": "10s",
                "sourceOnDemandCloseAfter": "30s",
            }

        mediamtx_config = {
            "logLevel": "info",
            "logDestinations": ["stdout"],

            # RTSP server settings
            "rtsp": True,
            "protocols": ["tcp"],
            "rtspAddress": f":{self.config.rtsp_port}",

            # HLS server settings
            "hls": True,
            "hlsAddress": f":{self.config.hls_port}",
            "hlsAlwaysRemux": False,
            "hlsSegmentCount": 3,
            "hlsSegmentDuration": "1s",
            "hlsPartDuration": "200ms",
            "hlsSegmentMaxSize": "50M",
            "hlsAllowOrigin": "*",

            # Paths (camera streams)
            "paths": paths
        }

        with open(config_path, 'w') as f:
            yaml.dump(mediamtx_config, f, default_flow_style=False)

        logger.info(
            "MediaMTX configuration generated",
            path=str(config_path),
            stream_count=len(self.cameras)
        )

    def get_status(self) -> dict:
        """Get stream server status."""
        return {
            "running": self.running,
            "pid": self.process.pid if self.process else None,
            "rtsp_port": self.config.rtsp_port,
            "hls_port": self.config.hls_port,
            "streams": [
                {
                    "camera_id": cam.id,
                    "hls_url": f"http://localhost:{self.config.hls_port}/{cam.id}/index.m3u8"
                }
                for cam in self.cameras
            ]
        }

    def get_hls_url(self, camera_id: str) -> Optional[str]:
        """Get HLS URL for a camera."""
        for cam in self.cameras:
            if cam.id == camera_id:
                return f"http://localhost:{self.config.hls_port}/{camera_id}/index.m3u8"
        return None

    def get_rtsp_url(self, camera_id: str, main: bool = False) -> Optional[str]:
        """Get RTSP URL for a camera."""
        for cam in self.cameras:
            if cam.id == camera_id:
                suffix = "-main" if main else ""
                return f"rtsp://localhost:{self.config.rtsp_port}/{camera_id}{suffix}"
        return None

    async def restart(self):
        """Restart the stream server."""
        logger.info("Restarting MediaMTX")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()
