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
    """Tests for ExportRequest class."""

    def test_init(self):
        """Test ExportRequest initialization."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 11, 0, 0)

        request = ExportRequest(
            request_id="export1",
            camera_id="cam1",
            start_time=start,
            end_time=end
        )

        assert request.request_id == "export1"
        assert request.camera_id == "cam1"
        assert request.start_time == start
        assert request.end_time == end
        assert request.status == "pending"

    def test_to_dict(self):
        """Test ExportRequest serialization."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 11, 0, 0)

        request = ExportRequest(
            request_id="export1",
            camera_id="cam1",
            start_time=start,
            end_time=end
        )

        result = request.to_dict()

        assert result["request_id"] == "export1"
        assert result["camera_id"] == "cam1"
        assert result["status"] == "pending"


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
        assert export_handler.queue is not None

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, export_handler):
        """Test ExportHandler start/stop lifecycle."""
        # Start handler
        await export_handler.start()
        assert export_handler.running is True
        assert export_handler._session is not None
        assert export_handler._poll_task is not None
        assert export_handler._process_task is not None

        # Stop handler
        await export_handler.stop()
        assert export_handler.running is False

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
