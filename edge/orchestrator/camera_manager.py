"""
Ziskin Field Systems - Camera Manager Module

Handles camera connectivity verification and status monitoring.
"""

import asyncio
import aiohttp
import structlog
from datetime import datetime
from typing import Optional, List, Dict

from .config import CameraConfig

logger = structlog.get_logger(__name__)


class CameraStatus:
    """Represents the status of a camera."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.online = False
        self.last_seen: Optional[datetime] = None
        self.rtsp_main_ok = False
        self.rtsp_sub_ok = False
        self.onvif_ok = False
        self.error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "online": self.online,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "rtsp_main_ok": self.rtsp_main_ok,
            "rtsp_sub_ok": self.rtsp_sub_ok,
            "onvif_ok": self.onvif_ok,
            "error_message": self.error_message
        }


class CameraManager:
    """Manages camera connectivity and status."""

    def __init__(self, cameras: List[CameraConfig]):
        self.cameras = {cam.id: cam for cam in cameras}
        self.status: Dict[str, CameraStatus] = {
            cam.id: CameraStatus(cam.id) for cam in cameras
        }

    async def verify_all_cameras(self) -> Dict[str, bool]:
        """Verify connectivity for all cameras."""
        logger.info("Verifying camera connectivity", count=len(self.cameras))

        tasks = [
            self.verify_camera(camera_id)
            for camera_id in self.cameras
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        connected = sum(1 for r in results if r is True)
        logger.info(
            "Camera verification complete",
            connected=connected,
            total=len(self.cameras)
        )

        return {
            camera_id: results[i] if not isinstance(results[i], Exception) else False
            for i, camera_id in enumerate(self.cameras)
        }

    async def verify_camera(self, camera_id: str) -> bool:
        """Verify connectivity for a single camera."""
        if camera_id not in self.cameras:
            logger.error("Unknown camera ID", camera_id=camera_id)
            return False

        camera = self.cameras[camera_id]
        status = self.status[camera_id]

        logger.debug("Verifying camera", camera_id=camera_id, ip=camera.ip)

        try:
            # Check RTSP connectivity via simple TCP connection
            rtsp_main_ok = await self._check_rtsp_port(camera.ip, 554)
            rtsp_sub_ok = rtsp_main_ok  # Same port for both streams

            # Check ONVIF connectivity
            onvif_ok = await self._check_onvif(camera)

            status.rtsp_main_ok = rtsp_main_ok
            status.rtsp_sub_ok = rtsp_sub_ok
            status.onvif_ok = onvif_ok
            status.online = rtsp_main_ok or onvif_ok
            status.last_seen = datetime.now() if status.online else status.last_seen
            status.error_message = None

            logger.info(
                "Camera verification result",
                camera_id=camera_id,
                online=status.online,
                rtsp_ok=rtsp_main_ok,
                onvif_ok=onvif_ok
            )

            return status.online

        except Exception as e:
            status.online = False
            status.error_message = str(e)
            logger.error(
                "Camera verification failed",
                camera_id=camera_id,
                error=str(e)
            )
            return False

    async def _check_rtsp_port(self, ip: str, port: int = 554) -> bool:
        """Check if RTSP port is accessible."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False

    async def _check_onvif(self, camera: CameraConfig) -> bool:
        """Check if ONVIF service is accessible."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{camera.ip}:{camera.onvif_port}/onvif/device_service",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    # ONVIF services typically return 400 for GET requests
                    # but the endpoint being reachable is what we care about
                    return response.status in [200, 400, 401, 405]
        except Exception:
            return False

    async def get_status(self) -> List[dict]:
        """Get status for all cameras."""
        return [status.to_dict() for status in self.status.values()]

    async def get_camera_status(self, camera_id: str) -> Optional[dict]:
        """Get status for a specific camera."""
        if camera_id in self.status:
            return self.status[camera_id].to_dict()
        return None

    def get_camera_config(self, camera_id: str) -> Optional[CameraConfig]:
        """Get configuration for a specific camera."""
        return self.cameras.get(camera_id)

    async def start_monitoring(self, check_interval: int = 60):
        """Start continuous camera monitoring."""
        logger.info("Starting camera monitoring", interval=check_interval)

        while True:
            try:
                await self.verify_all_cameras()
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                logger.info("Camera monitoring stopped")
                break
            except Exception as e:
                logger.error("Error in camera monitoring", error=str(e))
                await asyncio.sleep(check_interval)
