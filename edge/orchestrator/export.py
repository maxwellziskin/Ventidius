"""
Ziskin Field Systems - Export Handler Module

Handles clip export requests from cloud platform.
"""

import asyncio
import aiohttp
import structlog
from pathlib import Path
from datetime import datetime
from typing import Optional
import subprocess
import tempfile
import os

from config import StorageConfig, CloudConfig

logger = structlog.get_logger(__name__)


class ExportRequest:
    """Represents an export request."""

    def __init__(
        self,
        request_id: str,
        camera_id: str,
        start_time: datetime,
        end_time: datetime
    ):
        self.request_id = request_id
        self.camera_id = camera_id
        self.start_time = start_time
        self.end_time = end_time
        self.status = "pending"
        self.output_path: Optional[Path] = None
        self.file_size: int = 0
        self.error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "camera_id": self.camera_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status,
            "output_path": str(self.output_path) if self.output_path else None,
            "file_size": self.file_size,
            "error_message": self.error_message
        }


class ExportHandler:
    """Handles clip export requests."""

    def __init__(self, storage_config: StorageConfig, cloud_config: CloudConfig):
        self.storage_config = storage_config
        self.cloud_config = cloud_config
        self.running = False
        self.queue: asyncio.Queue[ExportRequest] = asyncio.Queue()
        self._poll_task: Optional[asyncio.Task] = None
        self._process_task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Start export handler."""
        logger.info("Starting export handler")
        self.running = True
        self._session = aiohttp.ClientSession()

        # Start polling for export requests
        self._poll_task = asyncio.create_task(self._poll_for_requests())

        # Start processing queue
        self._process_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        """Stop export handler."""
        logger.info("Stopping export handler")
        self.running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()

    async def _poll_for_requests(self):
        """Poll cloud API for pending export requests."""
        while self.running:
            try:
                url = f"{self.cloud_config.api_endpoint}/api/edge/exports/pending"

                async with self._session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.cloud_config.api_key}"
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for req_data in data.get("requests", []):
                            request = ExportRequest(
                                request_id=req_data["id"],
                                camera_id=req_data["camera_id"],
                                start_time=datetime.fromisoformat(req_data["start_time"]),
                                end_time=datetime.fromisoformat(req_data["end_time"])
                            )
                            await self.queue.put(request)
                            logger.info(
                                "Export request queued",
                                request_id=request.request_id,
                                camera_id=request.camera_id
                            )

                await asyncio.sleep(30)  # Poll every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error polling for export requests", error=str(e))
                await asyncio.sleep(60)

    async def _process_queue(self):
        """Process export requests from queue."""
        while self.running:
            try:
                # Get next request (with timeout to allow checking running flag)
                try:
                    request = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    continue

                logger.info(
                    "Processing export request",
                    request_id=request.request_id,
                    camera_id=request.camera_id
                )

                # Update status to processing
                request.status = "processing"
                await self._update_request_status(request)

                try:
                    # Find and merge recording files
                    output_path = await self._create_export(request)

                    if output_path and output_path.exists():
                        request.output_path = output_path
                        request.file_size = output_path.stat().st_size
                        request.status = "uploading"
                        await self._update_request_status(request)

                        # Upload to cloud
                        upload_url = await self._upload_export(request)

                        if upload_url:
                            request.status = "completed"
                            logger.info(
                                "Export completed",
                                request_id=request.request_id,
                                file_size=request.file_size
                            )
                        else:
                            request.status = "failed"
                            request.error_message = "Upload failed"
                    else:
                        request.status = "failed"
                        request.error_message = "No recordings found for time range"

                except Exception as e:
                    request.status = "failed"
                    request.error_message = str(e)
                    logger.error(
                        "Export failed",
                        request_id=request.request_id,
                        error=str(e)
                    )

                await self._update_request_status(request)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error processing export queue", error=str(e))
                await asyncio.sleep(5)

    async def _create_export(self, request: ExportRequest) -> Optional[Path]:
        """Create export file by merging recording segments."""
        storage_path = Path(self.storage_config.path)
        camera_path = storage_path / request.camera_id

        if not camera_path.exists():
            logger.warning(
                "Camera directory not found",
                camera_id=request.camera_id
            )
            return None

        # Find all relevant recording files
        recording_files = []
        current_date = request.start_time.date()
        end_date = request.end_time.date()

        while current_date <= end_date:
            date_dir = camera_path / current_date.strftime("%Y-%m-%d")

            if date_dir.exists():
                for file in sorted(date_dir.glob("*.mp4")):
                    try:
                        time_str = file.stem
                        file_time = datetime.strptime(
                            f"{current_date} {time_str}",
                            "%Y-%m-%d %H-%M-%S"
                        )

                        # Check if file overlaps with requested range
                        file_end = file_time.replace(
                            minute=file_time.minute + 30
                        )

                        if file_time <= request.end_time and file_end >= request.start_time:
                            recording_files.append(file)

                    except ValueError:
                        continue

            current_date = current_date.replace(
                day=current_date.day + 1
            )

        if not recording_files:
            return None

        logger.info(
            "Found recording files for export",
            count=len(recording_files),
            request_id=request.request_id
        )

        # Create output file
        output_dir = Path(tempfile.gettempdir()) / "zfs_exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{request.request_id}.mp4"

        if len(recording_files) == 1:
            # Single file, just copy (or trim if needed)
            await self._trim_video(
                recording_files[0],
                output_file,
                request.start_time,
                request.end_time
            )
        else:
            # Multiple files, concatenate
            await self._concat_videos(recording_files, output_file)

        return output_file if output_file.exists() else None

    async def _trim_video(
        self,
        input_path: Path,
        output_path: Path,
        start_time: datetime,
        end_time: datetime
    ):
        """Trim video to specified time range."""
        duration = (end_time - start_time).total_seconds()

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-t", str(duration),
            "-c", "copy",
            "-y",
            str(output_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.wait()

    async def _concat_videos(self, input_files: list[Path], output_path: Path):
        """Concatenate multiple video files."""
        # Create concat list file
        concat_file = output_path.parent / f"{output_path.stem}_concat.txt"

        with open(concat_file, 'w') as f:
            for file in input_files:
                f.write(f"file '{file}'\n")

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-y",
            str(output_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.wait()

        # Clean up concat file
        concat_file.unlink(missing_ok=True)

    async def _upload_export(self, request: ExportRequest) -> Optional[str]:
        """Upload export file to cloud storage."""
        if not request.output_path or not request.output_path.exists():
            return None

        url = f"{self.cloud_config.api_endpoint}/api/edge/exports/{request.request_id}/upload"

        try:
            with open(request.output_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field(
                    'file',
                    f,
                    filename=request.output_path.name,
                    content_type='video/mp4'
                )

                async with self._session.post(
                    url,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {self.cloud_config.api_key}"
                    },
                    timeout=aiohttp.ClientTimeout(total=3600)  # 1 hour timeout for large files
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("download_url")
                    else:
                        logger.error(
                            "Upload failed",
                            status=response.status,
                            response=await response.text()
                        )
                        return None

        except Exception as e:
            logger.error("Error uploading export", error=str(e))
            return None

        finally:
            # Clean up local file
            request.output_path.unlink(missing_ok=True)

    async def _update_request_status(self, request: ExportRequest):
        """Update export request status in cloud."""
        url = f"{self.cloud_config.api_endpoint}/api/edge/exports/{request.request_id}/status"

        try:
            async with self._session.put(
                url,
                json={
                    "status": request.status,
                    "file_size": request.file_size,
                    "error_message": request.error_message
                },
                headers={
                    "Authorization": f"Bearer {self.cloud_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "Failed to update export status",
                        request_id=request.request_id,
                        status=response.status
                    )

        except Exception as e:
            logger.error(
                "Error updating export status",
                request_id=request.request_id,
                error=str(e)
            )
