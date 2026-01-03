"""
Tests for cameras router.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestListCameras:
    """Tests for list_cameras endpoint."""

    @pytest.mark.asyncio
    async def test_admin_sees_all_cameras(self, mock_db_session, mock_admin_user, sample_camera):
        """Test that admin users can see all cameras."""
        from routers.cameras import list_cameras

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_camera]
        mock_db_session.execute.return_value = mock_result

        result = await list_cameras(mock_admin_user, mock_db_session)

        assert len(result) == 1


class TestCreateCamera:
    """Tests for create_camera endpoint."""

    @pytest.mark.asyncio
    async def test_create_camera_site_not_found(self, mock_db_session, mock_admin_user):
        """Test creating camera for non-existent site."""
        from routers.cameras import create_camera
        from schemas.camera import CameraCreate
        from fastapi import HTTPException

        camera_data = CameraCreate(
            site_id=uuid4(),
            name="New Camera",
            local_ip="192.168.1.50",
            rtsp_path="/stream1"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await create_camera(camera_data, mock_admin_user, mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_camera_success(self, mock_db_session, mock_admin_user, sample_site):
        """Test successful camera creation."""
        from routers.cameras import create_camera
        from schemas.camera import CameraCreate

        camera_data = CameraCreate(
            site_id=sample_site.id,
            name="New Camera",
            local_ip="192.168.1.50",
            rtsp_path="/stream1"
        )

        # First call returns site, second is for other queries
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_site
        mock_db_session.execute.return_value = mock_result

        mock_camera = MagicMock()
        mock_camera.id = uuid4()
        mock_camera.name = "New Camera"
        mock_camera.to_dict = MagicMock(return_value={
            "id": str(mock_camera.id),
            "name": "New Camera"
        })

        with patch('routers.cameras.Camera', return_value=mock_camera):
            result = await create_camera(camera_data, mock_admin_user, mock_db_session)

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()


class TestDeleteCamera:
    """Tests for delete_camera endpoint."""

    @pytest.mark.asyncio
    async def test_delete_camera_not_found(self, mock_db_session, mock_admin_user):
        """Test deleting non-existent camera."""
        from routers.cameras import delete_camera
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_camera(uuid4(), mock_admin_user, mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_camera_success(self, mock_db_session, mock_admin_user, sample_camera):
        """Test successful camera deletion."""
        from routers.cameras import delete_camera

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_camera
        mock_db_session.execute.return_value = mock_result

        await delete_camera(sample_camera.id, mock_admin_user, mock_db_session)

        # Verify delete was called synchronously (not awaited - tests our fix)
        mock_db_session.delete.assert_called_once_with(sample_camera)
        mock_db_session.commit.assert_called_once()


class TestGetStreamUrl:
    """Tests for get_stream_url endpoint."""

    @pytest.mark.asyncio
    async def test_get_stream_url_camera_not_found(self, mock_db_session, mock_admin_user):
        """Test getting stream URL for non-existent camera."""
        from routers.cameras import get_stream_url
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            await get_stream_url(uuid4(), mock_admin_user, mock_request, mock_db_session)

        assert exc_info.value.status_code == 404
