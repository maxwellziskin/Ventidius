"""
Ziskin Field Systems - PTZ Handler Module

Handles PTZ (Pan-Tilt-Zoom) control via ONVIF protocol.
"""

import asyncio
import structlog
from typing import Optional, List, Dict
from datetime import datetime
import websockets
import json

from .config import CameraConfig, CloudConfig
from .utils.onvif_client import ONVIFClient

logger = structlog.get_logger(__name__)


class PTZPreset:
    """Represents a PTZ preset position."""

    def __init__(self, preset_id: int, name: str, pan: float, tilt: float, zoom: float):
        self.preset_id = preset_id
        self.name = name
        self.pan = pan
        self.tilt = tilt
        self.zoom = zoom

    def to_dict(self) -> dict:
        return {
            "preset_id": self.preset_id,
            "name": self.name,
            "pan": self.pan,
            "tilt": self.tilt,
            "zoom": self.zoom
        }


class PTZHandler:
    """Handles PTZ control for cameras via ONVIF."""

    # Rate limiting: max 10 commands per second per camera
    RATE_LIMIT_WINDOW = 1.0
    MAX_COMMANDS_PER_WINDOW = 10

    def __init__(self, cameras: List[CameraConfig]):
        self.cameras = {cam.id: cam for cam in cameras if cam.ptz}
        self.onvif_clients: Dict[str, ONVIFClient] = {}
        self.presets: Dict[str, List[PTZPreset]] = {}
        self.command_timestamps: Dict[str, List[datetime]] = {}
        self.running = False
        self._ws_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize ONVIF clients for all PTZ cameras."""
        logger.info("Initializing PTZ handler", camera_count=len(self.cameras))

        for camera_id, camera in self.cameras.items():
            try:
                client = ONVIFClient(
                    host=camera.ip,
                    port=camera.onvif_port,
                    username=camera.username,
                    password=camera.password
                )
                await client.connect()
                self.onvif_clients[camera_id] = client

                # Load presets
                presets = await client.get_presets()
                self.presets[camera_id] = [
                    PTZPreset(
                        preset_id=p["id"],
                        name=p["name"],
                        pan=p.get("pan", 0),
                        tilt=p.get("tilt", 0),
                        zoom=p.get("zoom", 0)
                    )
                    for p in presets
                ]

                logger.info(
                    "PTZ camera initialized",
                    camera_id=camera_id,
                    preset_count=len(self.presets[camera_id])
                )

            except Exception as e:
                logger.error(
                    "Failed to initialize PTZ camera",
                    camera_id=camera_id,
                    error=str(e)
                )

        self.running = True

    async def stop(self):
        """Stop PTZ handler and disconnect clients."""
        logger.info("Stopping PTZ handler")
        self.running = False

        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        for camera_id, client in self.onvif_clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(
                    "Error disconnecting ONVIF client",
                    camera_id=camera_id,
                    error=str(e)
                )

        self.onvif_clients.clear()
        logger.info("PTZ handler stopped")

    def _check_rate_limit(self, camera_id: str) -> bool:
        """Check if command is within rate limit."""
        now = datetime.now()
        window_start = now.timestamp() - self.RATE_LIMIT_WINDOW

        # Initialize timestamps list if needed
        if camera_id not in self.command_timestamps:
            self.command_timestamps[camera_id] = []

        # Remove old timestamps
        self.command_timestamps[camera_id] = [
            ts for ts in self.command_timestamps[camera_id]
            if ts.timestamp() > window_start
        ]

        # Check limit
        if len(self.command_timestamps[camera_id]) >= self.MAX_COMMANDS_PER_WINDOW:
            return False

        # Record this command
        self.command_timestamps[camera_id].append(now)
        return True

    async def move(
        self,
        camera_id: str,
        pan: float = 0,
        tilt: float = 0,
        zoom: float = 0
    ) -> bool:
        """Execute continuous move command."""
        if camera_id not in self.onvif_clients:
            logger.warning("Camera not found or not PTZ enabled", camera_id=camera_id)
            return False

        if not self._check_rate_limit(camera_id):
            logger.warning("Rate limit exceeded", camera_id=camera_id)
            return False

        try:
            client = self.onvif_clients[camera_id]
            await client.continuous_move(pan=pan, tilt=tilt, zoom=zoom)
            logger.debug(
                "PTZ move command sent",
                camera_id=camera_id,
                pan=pan,
                tilt=tilt,
                zoom=zoom
            )
            return True
        except Exception as e:
            logger.error(
                "PTZ move command failed",
                camera_id=camera_id,
                error=str(e)
            )
            return False

    async def stop_movement(self, camera_id: str) -> bool:
        """Stop all PTZ movement."""
        if camera_id not in self.onvif_clients:
            return False

        if not self._check_rate_limit(camera_id):
            return False

        try:
            client = self.onvif_clients[camera_id]
            await client.stop()
            logger.debug("PTZ stop command sent", camera_id=camera_id)
            return True
        except Exception as e:
            logger.error(
                "PTZ stop command failed",
                camera_id=camera_id,
                error=str(e)
            )
            return False

    async def goto_preset(self, camera_id: str, preset_id: int) -> bool:
        """Move camera to a preset position."""
        if camera_id not in self.onvif_clients:
            return False

        if not self._check_rate_limit(camera_id):
            return False

        try:
            client = self.onvif_clients[camera_id]
            await client.goto_preset(preset_id)
            logger.info(
                "PTZ goto preset command sent",
                camera_id=camera_id,
                preset_id=preset_id
            )
            return True
        except Exception as e:
            logger.error(
                "PTZ goto preset failed",
                camera_id=camera_id,
                preset_id=preset_id,
                error=str(e)
            )
            return False

    async def set_preset(self, camera_id: str, preset_name: str) -> Optional[int]:
        """Save current position as a new preset."""
        if camera_id not in self.onvif_clients:
            return None

        try:
            client = self.onvif_clients[camera_id]
            preset_id = await client.set_preset(preset_name)

            # Update local preset list
            position = await client.get_position()
            preset = PTZPreset(
                preset_id=preset_id,
                name=preset_name,
                pan=position.get("pan", 0),
                tilt=position.get("tilt", 0),
                zoom=position.get("zoom", 0)
            )

            if camera_id not in self.presets:
                self.presets[camera_id] = []
            self.presets[camera_id].append(preset)

            logger.info(
                "PTZ preset saved",
                camera_id=camera_id,
                preset_id=preset_id,
                preset_name=preset_name
            )
            return preset_id

        except Exception as e:
            logger.error(
                "Failed to set PTZ preset",
                camera_id=camera_id,
                error=str(e)
            )
            return None

    def get_presets(self, camera_id: str) -> List[dict]:
        """Get presets for a camera."""
        if camera_id not in self.presets:
            return []
        return [p.to_dict() for p in self.presets[camera_id]]

    async def start_command_listener(self, cloud_config: CloudConfig):
        """Start WebSocket listener for PTZ commands from cloud."""
        self._ws_task = asyncio.create_task(
            self._websocket_listener(cloud_config)
        )

    async def _websocket_listener(self, cloud_config: CloudConfig):
        """WebSocket listener for PTZ commands."""
        ws_url = cloud_config.api_endpoint.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/ws/ptz"

        while self.running:
            try:
                async with websockets.connect(
                    ws_url,
                    extra_headers={"Authorization": f"Bearer {cloud_config.api_key}"}
                ) as ws:
                    logger.info("Connected to PTZ command WebSocket")

                    async for message in ws:
                        if not self.running:
                            break

                        try:
                            command = json.loads(message)
                            await self._handle_command(command)
                        except json.JSONDecodeError:
                            logger.warning("Invalid PTZ command format")

            except websockets.ConnectionClosed:
                logger.warning("PTZ WebSocket connection closed, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("PTZ WebSocket error", error=str(e))
                await asyncio.sleep(5)

    async def _handle_command(self, command: dict):
        """Handle a PTZ command from cloud."""
        camera_id = command.get("camera_id")
        action = command.get("action")

        if not camera_id or not action:
            logger.warning("Invalid PTZ command", command=command)
            return

        if action == "move":
            await self.move(
                camera_id,
                pan=command.get("pan", 0),
                tilt=command.get("tilt", 0),
                zoom=command.get("zoom", 0)
            )
        elif action == "stop":
            await self.stop_movement(camera_id)
        elif action == "preset":
            preset_id = command.get("preset_id")
            if preset_id is not None:
                await self.goto_preset(camera_id, preset_id)
        else:
            logger.warning("Unknown PTZ action", action=action)
