"""
Tests for admin router.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestListClients:
    """Tests for list_clients endpoint."""

    @pytest.mark.asyncio
    async def test_list_clients(self, mock_db_session, mock_admin_user, sample_client):
        """Test listing all clients."""
        from routers.admin import list_clients

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_client]
        mock_db_session.execute.return_value = mock_result

        result = await list_clients(mock_admin_user, mock_db_session)

        assert len(result) == 1


class TestCreateClient:
    """Tests for create_client endpoint."""

    @pytest.mark.asyncio
    async def test_create_client_success(self, mock_db_session, mock_admin_user):
        """Test successful client creation."""
        from routers.admin import create_client
        from schemas.client import ClientCreate

        client_data = ClientCreate(
            name="New Client",
            contact_email="newclient@example.com"
        )

        mock_client = MagicMock()
        mock_client.id = uuid4()
        mock_client.name = "New Client"
        mock_client.to_dict = MagicMock(return_value={
            "id": str(mock_client.id),
            "name": "New Client"
        })

        with patch('routers.admin.Client', return_value=mock_client):
            result = await create_client(client_data, mock_admin_user, mock_db_session)

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()


class TestDeleteClient:
    """Tests for delete_client endpoint."""

    @pytest.mark.asyncio
    async def test_delete_client_not_found(self, mock_db_session, mock_admin_user):
        """Test deleting non-existent client."""
        from routers.admin import delete_client
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_client(uuid4(), mock_admin_user, mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_client_success(self, mock_db_session, mock_admin_user, sample_client):
        """Test successful client deletion."""
        from routers.admin import delete_client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_client
        mock_db_session.execute.return_value = mock_result

        await delete_client(sample_client.id, mock_admin_user, mock_db_session)

        # Verify delete was called synchronously (tests our fix)
        mock_db_session.delete.assert_called_once_with(sample_client)
        mock_db_session.commit.assert_called_once()


class TestGetStats:
    """Tests for get_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_db_session, mock_admin_user):
        """Test getting system statistics."""
        from routers.admin import get_stats

        # Mock all the count queries
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db_session.execute.return_value = mock_result

        result = await get_stats(mock_admin_user, mock_db_session)

        assert "clients" in result
        assert "sites" in result
        assert "cameras" in result
        assert "users" in result


class TestEdgeHealthReporting:
    """Tests for edge device health reporting."""

    @pytest.mark.asyncio
    async def test_report_health_site_not_found(self, mock_db_session):
        """Test health report for non-existent site."""
        from routers.admin import report_health
        from schemas.site import SiteHealth
        from fastapi import HTTPException

        mock_edge = {"site_id": str(uuid4()), "site_name": "Test Site"}
        health_data = SiteHealth(
            site_id=mock_edge["site_id"],
            system={},
            application={"cameras": []}
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await report_health(health_data, mock_edge, mock_db_session)

        assert exc_info.value.status_code == 404
