#!/usr/bin/env python3
"""
Ziskin Field Systems - Edge Device Orchestrator Main Daemon

The main entry point that coordinates all edge device operations:
- Camera connectivity verification
- MediaMTX and FFmpeg process management
- Health reporting to cloud
- PTZ command handling
- Disk space management
- Graceful shutdown on UPS signals
"""

import asyncio
import signal
import sys
import argparse
import structlog
from pathlib import Path

from config import load_config, SiteConfig
from camera_manager import CameraManager
from stream_manager import StreamManager
from recording import RecordingManager
from ptz_handler import PTZHandler
from health import HealthReporter
from export import ExportHandler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Main orchestrator daemon for edge device operations."""

    def __init__(self, config: SiteConfig):
        self.config = config
        self.running = False
        self.shutdown_event = asyncio.Event()

        # Initialize managers
        self.camera_manager = CameraManager(config.cameras)
        self.stream_manager = StreamManager(config.mediamtx, config.cameras)
        self.recording_manager = RecordingManager(
            config.storage,
            config.recording,
            config.cameras
        )
        self.ptz_handler = PTZHandler(config.cameras)
        self.health_reporter = HealthReporter(
            config.site_id,
            config.cloud,
            config.health
        )
        self.export_handler = ExportHandler(
            config.storage,
            config.cloud
        )

    async def start(self):
        """Start all orchestrator components."""
        logger.info(
            "Starting Ziskin Field Systems Orchestrator",
            site_id=self.config.site_id,
            site_name=self.config.site_name,
            camera_count=len(self.config.cameras)
        )

        self.running = True

        try:
            # Verify camera connectivity
            await self.camera_manager.verify_all_cameras()

            # Start stream server (MediaMTX)
            await self.stream_manager.start()

            # Start recording processes
            await self.recording_manager.start()

            # Initialize PTZ handler
            await self.ptz_handler.initialize()

            # Start health reporting
            health_task = asyncio.create_task(
                self.health_reporter.start(self._get_health_data)
            )

            # Start export handler
            export_task = asyncio.create_task(
                self.export_handler.start()
            )

            # Start disk space monitor
            disk_task = asyncio.create_task(
                self._monitor_disk_space()
            )

            # Start PTZ command listener
            ptz_task = asyncio.create_task(
                self.ptz_handler.start_command_listener(self.config.cloud)
            )

            logger.info("All components started successfully")

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error("Error during orchestrator startup", error=str(e))
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop all orchestrator components gracefully."""
        if not self.running:
            return

        logger.info("Initiating graceful shutdown")
        self.running = False

        # Stop components in reverse order
        try:
            await self.export_handler.stop()
            await self.ptz_handler.stop()
            await self.health_reporter.stop()
            await self.recording_manager.stop()
            await self.stream_manager.stop()

            logger.info("Graceful shutdown completed")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))

    async def _get_health_data(self) -> dict:
        """Collect health data from all components."""
        return {
            "site_id": self.config.site_id,
            "cameras": await self.camera_manager.get_status(),
            "streams": self.stream_manager.get_status(),
            "recording": self.recording_manager.get_status(),
            "storage": await self._get_storage_status(),
        }

    async def _get_storage_status(self) -> dict:
        """Get storage usage information."""
        import shutil
        storage_path = Path(self.config.storage.path)

        if not storage_path.exists():
            return {"available": False}

        total, used, free = shutil.disk_usage(storage_path)
        return {
            "available": True,
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "usage_percent": round((used / total) * 100, 1)
        }

    async def _monitor_disk_space(self):
        """Monitor disk space and enforce retention policy."""
        while self.running:
            try:
                storage_status = await self._get_storage_status()

                if storage_status.get("available"):
                    usage_percent = storage_status.get("usage_percent", 0)

                    if usage_percent >= self.config.storage.max_usage_percent:
                        logger.warning(
                            "Storage usage exceeds threshold",
                            usage_percent=usage_percent,
                            threshold=self.config.storage.max_usage_percent
                        )
                        await self.recording_manager.cleanup_old_recordings()

                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error monitoring disk space", error=str(e))
                await asyncio.sleep(60)

    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, initiating shutdown")
        self.shutdown_event.set()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ziskin Field Systems Edge Orchestrator"
    )
    parser.add_argument(
        "-c", "--config",
        default="/opt/ziskin/config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        logger.error("Configuration file not found", path=args.config)
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to load configuration", error=str(e))
        sys.exit(1)

    # Create and start orchestrator
    orchestrator = Orchestrator(config)

    # Register signal handlers
    signal.signal(signal.SIGTERM, orchestrator.handle_signal)
    signal.signal(signal.SIGINT, orchestrator.handle_signal)

    # Start the orchestrator
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(main())
