"""
Tests for edge device camera manager module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.camera_manager import CameraManager, CameraStatus
from orchestrator.config import CameraConfig


class TestCameraStatus:
    """Tests for CameraStatus class."""

    def test_init(self):
        """Test CameraStatus initialization."""
        status = CameraStatus("cam1")
        assert status.camera_id == "cam1"
        assert status.online is False
        assert status.last_seen is None
        assert status.rtsp_main_ok is False
        assert status.rtsp_sub_ok is False
        assert status.onvif_ok is False
        assert status.error_message is None

    def test_to_dict(self):
        """Test CameraStatus serialization."""
        status = CameraStatus("cam1")
        status.online = True
        status.last_seen = datetime(2024, 1, 1, 12, 0, 0)

        result = status.to_dict()

        assert result["camera_id"] == "cam1"
        assert result["online"] is True
        assert result["last_seen"] == "2024-01-01T12:00:00"
        assert result["rtsp_main_ok"] is False
        assert result["error_message"] is None

    def test_to_dict_no_last_seen(self):
        """Test CameraStatus serialization without last_seen."""
        status = CameraStatus("cam1")
        result = status.to_dict()
        assert result["last_seen"] is None


class TestCameraManager:
    """Tests for CameraManager class."""

    @pytest.fixture
    def sample_cameras(self):
        """Create sample camera configurations."""
        return [
            CameraConfig(
                id="cam1",
                name="Front Door",
                ip="192.168.1.10",
                rtsp_main="/stream1",
                rtsp_sub="/stream2",
                onvif_port=80
            ),
            CameraConfig(
                id="cam2",
                name="Back Door",
                ip="192.168.1.11",
                rtsp_main="/stream1",
                rtsp_sub="/stream2",
                onvif_port=80
            )
        ]

    @pytest.fixture
    def camera_manager(self, sample_cameras):
        """Create a CameraManager instance."""
        return CameraManager(sample_cameras)

    def test_init(self, camera_manager, sample_cameras):
        """Test CameraManager initialization."""
        assert len(camera_manager.cameras) == 2
        assert "cam1" in camera_manager.cameras
        assert "cam2" in camera_manager.cameras
        assert len(camera_manager.status) == 2

    @pytest.mark.asyncio
    async def test_verify_camera_unknown_id(self, camera_manager):
        """Test verify_camera with unknown camera ID."""
        result = await camera_manager.verify_camera("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_rtsp_port_success(self, camera_manager):
        """Test successful RTSP port check."""
        with patch('asyncio.open_connection') as mock_conn:
            mock_writer = MagicMock()
            mock_writer.close = MagicMock()
            mock_writer.wait_closed = AsyncMock()
            mock_conn.return_value = (MagicMock(), mock_writer)

            result = await camera_manager._check_rtsp_port("192.168.1.10", 554)
            assert result is True

    @pytest.mark.asyncio
    async def test_check_rtsp_port_timeout(self, camera_manager):
        """Test RTSP port check timeout."""
        with patch('asyncio.open_connection', side_effect=asyncio.TimeoutError):
            result = await camera_manager._check_rtsp_port("192.168.1.10", 554)
            assert result is False

    @pytest.mark.asyncio
    async def test_check_rtsp_port_connection_refused(self, camera_manager):
        """Test RTSP port check connection refused."""
        with patch('asyncio.open_connection', side_effect=ConnectionRefusedError):
            result = await camera_manager._check_rtsp_port("192.168.1.10", 554)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_status(self, camera_manager):
        """Test getting status for all cameras."""
        result = await camera_manager.get_status()
        assert len(result) == 2
        assert all(isinstance(s, dict) for s in result)

    @pytest.mark.asyncio
    async def test_get_camera_status_exists(self, camera_manager):
        """Test getting status for existing camera."""
        result = await camera_manager.get_camera_status("cam1")
        assert result is not None
        assert result["camera_id"] == "cam1"

    @pytest.mark.asyncio
    async def test_get_camera_status_not_exists(self, camera_manager):
        """Test getting status for non-existent camera."""
        result = await camera_manager.get_camera_status("unknown")
        assert result is None

    def test_get_camera_config_exists(self, camera_manager):
        """Test getting config for existing camera."""
        config = camera_manager.get_camera_config("cam1")
        assert config is not None
        assert config.id == "cam1"

    def test_get_camera_config_not_exists(self, camera_manager):
        """Test getting config for non-existent camera."""
        config = camera_manager.get_camera_config("unknown")
        assert config is None

    @pytest.mark.asyncio
    async def test_verify_all_cameras(self, camera_manager):
        """Test verifying all cameras."""
        with patch.object(camera_manager, 'verify_camera', new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            result = await camera_manager.verify_all_cameras()

            assert len(result) == 2
            assert mock_verify.call_count == 2
