"""
Ziskin Field Systems - Recording Module

Handles continuous recording with FFmpeg, including burned-in timestamps.
"""

import asyncio
import subprocess
import signal
import structlog
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import os

from config import StorageConfig, RecordingConfig, CameraConfig

logger = structlog.get_logger(__name__)


class RecordingProcess:
    """Represents an active FFmpeg recording process."""

    def __init__(self, camera_id: str, output_path: Path):
        self.camera_id = camera_id
        self.output_path = output_path
        self.process: Optional[subprocess.Popen] = None
        self.started_at: Optional[datetime] = None
        self.recording = False

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "output_path": str(self.output_path),
            "recording": self.recording,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "pid": self.process.pid if self.process else None
        }


class RecordingManager:
    """Manages FFmpeg recording processes for all cameras."""

    def __init__(
        self,
        storage_config: StorageConfig,
        recording_config: RecordingConfig,
        cameras: list[CameraConfig]
    ):
        self.storage_config = storage_config
        self.recording_config = recording_config
        self.cameras = {cam.id: cam for cam in cameras}
        self.recordings: dict[str, RecordingProcess] = {}
        self.running = False
        self._segment_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start recording for all cameras."""
        logger.info("Starting recording manager", camera_count=len(self.cameras))

        self.running = True

        # Ensure storage directory exists
        storage_path = Path(self.storage_config.path)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Start recording for each camera
        for camera_id, camera in self.cameras.items():
            await self._start_camera_recording(camera)

        # Start segment rotation task
        self._segment_task = asyncio.create_task(self._segment_rotation_loop())

        logger.info("Recording manager started")

    async def stop(self):
        """Stop all recordings gracefully."""
        logger.info("Stopping recording manager")
        self.running = False

        # Cancel segment rotation
        if self._segment_task:
            self._segment_task.cancel()
            try:
                await self._segment_task
            except asyncio.CancelledError:
                pass

        # Stop all recording processes
        for camera_id in list(self.recordings.keys()):
            await self._stop_camera_recording(camera_id)

        logger.info("Recording manager stopped")

    async def _start_camera_recording(self, camera: CameraConfig):
        """Start recording for a single camera."""
        now = datetime.now()
        date_dir = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")

        # Create output directory
        output_dir = Path(self.storage_config.path) / camera.id / date_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{time_str}.mp4"

        # Build FFmpeg command with burned-in timestamp
        timestamp_filter = self._build_timestamp_filter()

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", camera.rtsp_main_url,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-vf", timestamp_filter,
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "mp4",
            "-movflags", "+faststart",
            "-y",
            str(output_path)
        ]

        logger.info(
            "Starting camera recording",
            camera_id=camera.id,
            output=str(output_path)
        )

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
            )

            recording = RecordingProcess(camera.id, output_path)
            recording.process = process
            recording.started_at = now
            recording.recording = True

            self.recordings[camera.id] = recording

            logger.info(
                "Camera recording started",
                camera_id=camera.id,
                pid=process.pid
            )

        except Exception as e:
            logger.error(
                "Failed to start recording",
                camera_id=camera.id,
                error=str(e)
            )

    async def _stop_camera_recording(self, camera_id: str):
        """Stop recording for a single camera."""
        if camera_id not in self.recordings:
            return

        recording = self.recordings[camera_id]

        if recording.process:
            logger.info("Stopping camera recording", camera_id=camera_id)

            # Send SIGTERM for graceful stop
            recording.process.terminate()
            try:
                recording.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Recording did not stop gracefully, killing")
                recording.process.kill()

            recording.recording = False
            logger.info("Camera recording stopped", camera_id=camera_id)

        del self.recordings[camera_id]

    def _build_timestamp_filter(self) -> str:
        """Build FFmpeg drawtext filter for timestamp overlay."""
        font_size = self.recording_config.timestamp_font_size
        position = self.recording_config.timestamp_position

        # Map position to FFmpeg coordinates
        position_map = {
            "top-left": "x=10:y=10",
            "top-right": "x=w-tw-10:y=10",
            "bottom-left": "x=10:y=h-th-10",
            "bottom-right": "x=w-tw-10:y=h-th-10"
        }
        pos = position_map.get(position, "x=10:y=10")

        # Use localtime for the timestamp
        return (
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='%{{localtime\\:{self.recording_config.timestamp_format}}}':"
            f"fontcolor=white:fontsize={font_size}:"
            f"box=1:boxcolor=black@0.5:boxborderw=5:{pos}"
        )

    async def _segment_rotation_loop(self):
        """Rotate recording segments at configured intervals."""
        segment_duration = timedelta(
            minutes=self.recording_config.segment_duration_minutes
        )

        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = datetime.now()

                for camera_id, recording in list(self.recordings.items()):
                    if not recording.started_at:
                        continue

                    elapsed = now - recording.started_at

                    if elapsed >= segment_duration:
                        logger.info(
                            "Rotating recording segment",
                            camera_id=camera_id,
                            elapsed_minutes=elapsed.total_seconds() / 60
                        )

                        # Stop current recording
                        await self._stop_camera_recording(camera_id)

                        # Start new recording
                        if camera_id in self.cameras:
                            await self._start_camera_recording(
                                self.cameras[camera_id]
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in segment rotation", error=str(e))
                await asyncio.sleep(60)

    async def cleanup_old_recordings(self):
        """Remove recordings older than retention period."""
        retention_days = self.storage_config.retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        logger.info(
            "Cleaning up old recordings",
            retention_days=retention_days,
            cutoff_date=cutoff_date.isoformat()
        )

        storage_path = Path(self.storage_config.path)
        deleted_count = 0
        freed_bytes = 0

        for camera_dir in storage_path.iterdir():
            if not camera_dir.is_dir():
                continue

            for date_dir in camera_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # Delete all files in this directory
                        for file in date_dir.iterdir():
                            if file.is_file():
                                freed_bytes += file.stat().st_size
                                file.unlink()
                                deleted_count += 1

                        # Remove empty directory
                        date_dir.rmdir()
                        logger.debug(
                            "Removed old recording directory",
                            path=str(date_dir)
                        )
                except ValueError:
                    # Invalid date format, skip
                    continue
                except Exception as e:
                    logger.error(
                        "Error cleaning up directory",
                        path=str(date_dir),
                        error=str(e)
                    )

        logger.info(
            "Cleanup complete",
            deleted_files=deleted_count,
            freed_mb=round(freed_bytes / (1024 * 1024), 2)
        )

    def get_status(self) -> dict:
        """Get recording status for all cameras."""
        return {
            "running": self.running,
            "recordings": [r.to_dict() for r in self.recordings.values()],
            "storage_path": self.storage_config.path,
            "segment_duration_minutes": self.recording_config.segment_duration_minutes
        }

    async def get_recordings_for_camera(
        self,
        camera_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[Path]:
        """Get list of recording files for a camera within a time range."""
        storage_path = Path(self.storage_config.path)
        camera_path = storage_path / camera_id

        if not camera_path.exists():
            return []

        recordings = []
        current_date = start_time.date()
        end_date = end_time.date()

        while current_date <= end_date:
            date_dir = camera_path / current_date.strftime("%Y-%m-%d")

            if date_dir.exists():
                for file in sorted(date_dir.glob("*.mp4")):
                    try:
                        # Parse time from filename
                        time_str = file.stem  # e.g., "14-30-00"
                        file_time = datetime.strptime(
                            f"{current_date.isoformat()} {time_str}",
                            "%Y-%m-%d %H-%M-%S"
                        )

                        # Check if file is within range (with segment duration buffer)
                        segment_end = file_time + timedelta(
                            minutes=self.recording_config.segment_duration_minutes
                        )

                        if file_time <= end_time and segment_end >= start_time:
                            recordings.append(file)

                    except ValueError:
                        continue

            current_date += timedelta(days=1)

        return recordings
