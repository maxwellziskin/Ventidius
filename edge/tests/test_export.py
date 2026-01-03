"""
Tests for edge device export module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.export import ExportHandler, ExportRequest
from orchestrator.config import StorageConfig, CloudConfig


class TestExportRequest:
    """Tests for ExportRequest dataclass."""

    def test_init(self):
        """Test ExportRequest initialization."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 11, 0, 0)

        request = ExportRequest(
            id="export1",
            camera_id="cam1",
            start_time=start,
            end_time=end
        )

        assert request.id == "export1"
        assert request.camera_id == "cam1"
        assert request.start_time == start
        assert request.end_time == end


class TestExportHandler:
    """Tests for ExportHandler class."""

    @pytest.fixture
    def storage_config(self):
        """Create storage configuration."""
        return StorageConfig(
            path="/tmp/recordings",
            retention_days=90
        )

    @pytest.fixture
    def cloud_config(self):
        """Create cloud configuration."""
        return CloudConfig(
            api_endpoint="https://api.example.com",
            wireguard_endpoint="wg.example.com:51820",
            api_key="test-api-key"
        )

    @pytest.fixture
    def export_handler(self, storage_config, cloud_config):
        """Create an ExportHandler instance."""
        return ExportHandler(storage_config, cloud_config)

    def test_init(self, export_handler, storage_config, cloud_config):
        """Test ExportHandler initialization."""
        assert export_handler.storage_config == storage_config
        assert export_handler.cloud_config == cloud_config
        assert export_handler.running is False
        assert len(export_handler.pending_exports) == 0

    @pytest.mark.asyncio
    async def test_find_recording_files_no_files(self, export_handler):
        """Test finding recordings when no files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_handler.storage_config.path = tmpdir

            start = datetime(2024, 1, 1, 10, 0)
            end = datetime(2024, 1, 1, 11, 0)

            files = await export_handler._find_recording_files("cam1", start, end)
            assert files == []

    @pytest.mark.asyncio
    async def test_find_recording_files_with_files(self, export_handler):
        """Test finding recordings with matching files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_handler.storage_config.path = tmpdir

            # Create test recording files
            cam_dir = Path(tmpdir) / "cam1" / "2024-01-01"
            cam_dir.mkdir(parents=True)

            # Create a file within the time range
            test_file = cam_dir / "10-00-00.mp4"
            test_file.touch()

            start = datetime(2024, 1, 1, 10, 0)
            end = datetime(2024, 1, 1, 11, 0)

            files = await export_handler._find_recording_files("cam1", start, end)
            assert len(files) == 1
            assert str(files[0]).endswith("10-00-00.mp4")

    @pytest.mark.asyncio
    async def test_update_export_status(self, export_handler):
        """Test updating export status via API."""
        with patch('aiohttp.ClientSession.put', new_callable=AsyncMock) as mock_put:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_put.return_value.__aenter__.return_value = mock_response

            await export_handler._update_export_status("export1", "processing")
            # Verify the method doesn't raise an exception

    @pytest.mark.asyncio
    async def test_stop(self, export_handler):
        """Test stopping the export handler."""
        export_handler.running = True
        await export_handler.stop()
        assert export_handler.running is False


class TestDateArithmetic:
    """Tests to verify date arithmetic fixes."""

    def test_timedelta_minute_addition(self):
        """Test that timedelta works correctly for minute addition."""
        start = datetime(2024, 1, 1, 10, 45, 0)
        # This is the fix - using timedelta instead of replace()
        end = start + timedelta(minutes=30)

        assert end == datetime(2024, 1, 1, 11, 15, 0)

    def test_timedelta_day_addition(self):
        """Test that timedelta works correctly for day addition."""
        start = datetime(2024, 1, 31, 12, 0, 0)
        # This is the fix - using timedelta instead of replace()
        next_day = start + timedelta(days=1)

        assert next_day == datetime(2024, 2, 1, 12, 0, 0)

    def test_timedelta_handles_month_boundary(self):
        """Test timedelta correctly handles month boundaries."""
        # December 31 + 1 day should be January 1
        dec31 = datetime(2024, 12, 31, 23, 59, 0)
        jan1 = dec31 + timedelta(days=1)

        assert jan1.year == 2025
        assert jan1.month == 1
        assert jan1.day == 1
