"""
Ziskin Field Systems - ONVIF Client Utility

Wrapper around onvif-zeep for PTZ camera control.
"""

import asyncio
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class ONVIFClient:
    """ONVIF client for PTZ camera control."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._camera = None
        self._ptz_service = None
        self._media_service = None
        self._profile_token: Optional[str] = None
        self._connected = False

    async def connect(self):
        """Connect to ONVIF camera."""
        try:
            from onvif import ONVIFCamera

            # Run in executor since onvif-zeep is synchronous
            loop = asyncio.get_event_loop()

            def _connect():
                camera = ONVIFCamera(
                    self.host,
                    self.port,
                    self.username,
                    self.password
                )
                return camera

            self._camera = await loop.run_in_executor(None, _connect)

            # Get services
            self._ptz_service = await loop.run_in_executor(
                None,
                self._camera.create_ptz_service
            )
            self._media_service = await loop.run_in_executor(
                None,
                self._camera.create_media_service
            )

            # Get first media profile token
            profiles = await loop.run_in_executor(
                None,
                self._media_service.GetProfiles
            )

            if profiles:
                self._profile_token = profiles[0].token

            self._connected = True
            logger.info(
                "ONVIF connection established",
                host=self.host,
                profile_token=self._profile_token
            )

        except ImportError:
            logger.error("onvif-zeep not installed")
            raise
        except Exception as e:
            logger.error(
                "Failed to connect to ONVIF camera",
                host=self.host,
                error=str(e)
            )
            raise

    async def disconnect(self):
        """Disconnect from camera."""
        self._camera = None
        self._ptz_service = None
        self._media_service = None
        self._profile_token = None
        self._connected = False
        logger.debug("ONVIF disconnected", host=self.host)

    async def continuous_move(
        self,
        pan: float = 0,
        tilt: float = 0,
        zoom: float = 0
    ):
        """Execute continuous move command."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _move():
            request = self._ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self._profile_token
            request.Velocity = {
                'PanTilt': {'x': pan, 'y': tilt},
                'Zoom': {'x': zoom}
            }
            self._ptz_service.ContinuousMove(request)

        await loop.run_in_executor(None, _move)

    async def stop(self, pan_tilt: bool = True, zoom: bool = True):
        """Stop PTZ movement."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _stop():
            request = self._ptz_service.create_type('Stop')
            request.ProfileToken = self._profile_token
            request.PanTilt = pan_tilt
            request.Zoom = zoom
            self._ptz_service.Stop(request)

        await loop.run_in_executor(None, _stop)

    async def goto_preset(self, preset_token: int):
        """Move camera to preset position."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _goto():
            request = self._ptz_service.create_type('GotoPreset')
            request.ProfileToken = self._profile_token
            request.PresetToken = str(preset_token)
            self._ptz_service.GotoPreset(request)

        await loop.run_in_executor(None, _goto)

    async def set_preset(self, preset_name: str) -> int:
        """Save current position as preset."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _set():
            request = self._ptz_service.create_type('SetPreset')
            request.ProfileToken = self._profile_token
            request.PresetName = preset_name
            response = self._ptz_service.SetPreset(request)
            return int(response.PresetToken)

        return await loop.run_in_executor(None, _set)

    async def get_presets(self) -> list[dict]:
        """Get list of presets."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _get():
            presets = self._ptz_service.GetPresets({'ProfileToken': self._profile_token})
            result = []
            for preset in presets:
                preset_data = {
                    'id': int(preset.token) if preset.token else 0,
                    'name': preset.Name or f"Preset {preset.token}"
                }
                if hasattr(preset, 'PTZPosition') and preset.PTZPosition:
                    pos = preset.PTZPosition
                    if hasattr(pos, 'PanTilt') and pos.PanTilt:
                        preset_data['pan'] = pos.PanTilt.x
                        preset_data['tilt'] = pos.PanTilt.y
                    if hasattr(pos, 'Zoom') and pos.Zoom:
                        preset_data['zoom'] = pos.Zoom.x
                result.append(preset_data)
            return result

        return await loop.run_in_executor(None, _get)

    async def get_position(self) -> dict:
        """Get current PTZ position."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _get():
            status = self._ptz_service.GetStatus({'ProfileToken': self._profile_token})
            result = {}
            if hasattr(status, 'Position') and status.Position:
                pos = status.Position
                if hasattr(pos, 'PanTilt') and pos.PanTilt:
                    result['pan'] = pos.PanTilt.x
                    result['tilt'] = pos.PanTilt.y
                if hasattr(pos, 'Zoom') and pos.Zoom:
                    result['zoom'] = pos.Zoom.x
            return result

        return await loop.run_in_executor(None, _get)

    async def get_configurations(self) -> list[dict]:
        """Get PTZ configurations."""
        if not self._connected or not self._ptz_service:
            raise RuntimeError("Not connected to camera")

        loop = asyncio.get_event_loop()

        def _get():
            configs = self._ptz_service.GetConfigurations()
            return [
                {
                    'token': c.token,
                    'name': c.Name,
                    'pan_tilt_limits': {
                        'min_pan': c.PanTiltLimits.Range.XRange.Min if hasattr(c, 'PanTiltLimits') else -1,
                        'max_pan': c.PanTiltLimits.Range.XRange.Max if hasattr(c, 'PanTiltLimits') else 1,
                        'min_tilt': c.PanTiltLimits.Range.YRange.Min if hasattr(c, 'PanTiltLimits') else -1,
                        'max_tilt': c.PanTiltLimits.Range.YRange.Max if hasattr(c, 'PanTiltLimits') else 1,
                    } if hasattr(c, 'PanTiltLimits') else None,
                    'zoom_limits': {
                        'min': c.ZoomLimits.Range.XRange.Min if hasattr(c, 'ZoomLimits') else 0,
                        'max': c.ZoomLimits.Range.XRange.Max if hasattr(c, 'ZoomLimits') else 1,
                    } if hasattr(c, 'ZoomLimits') else None
                }
                for c in configs
            ]

        return await loop.run_in_executor(None, _get)
