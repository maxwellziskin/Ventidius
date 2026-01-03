"""
Tests for sites router.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestListSites:
    """Tests for list_sites endpoint."""

    @pytest.mark.asyncio
    async def test_admin_sees_all_sites(self, mock_db_session, mock_admin_user, sample_site):
        """Test that admin users can see all sites."""
        from routers.sites import list_sites

        # Mock the database response
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_site]
        mock_db_session.execute.return_value = mock_result

        result = await list_sites(mock_admin_user, mock_db_session)

        assert len(result) == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_sees_only_their_sites(self, mock_db_session, mock_client_user, sample_site):
        """Test that client users only see their own sites."""
        from routers.sites import list_sites

        sample_site.client_id = mock_client_user.client_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_site]
        mock_db_session.execute.return_value = mock_result

        result = await list_sites(mock_client_user, mock_db_session)

        assert len(result) == 1


class TestCreateSite:
    """Tests for create_site endpoint."""

    @pytest.mark.asyncio
    async def test_create_site_success(self, mock_db_session, mock_admin_user):
        """Test successful site creation."""
        from routers.sites import create_site
        from schemas.site import SiteCreate

        site_data = SiteCreate(
            client_id=uuid4(),
            name="New Site",
            address="456 New St"
        )

        # Mock the site object that would be created
        mock_site = MagicMock()
        mock_site.id = uuid4()
        mock_site.name = "New Site"
        mock_site.to_dict = MagicMock(return_value={
            "id": str(mock_site.id),
            "name": "New Site",
            "address": "456 New St"
        })

        # Patch Site class to return our mock
        with patch('routers.sites.Site', return_value=mock_site):
            result = await create_site(site_data, mock_admin_user, mock_db_session)

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()


class TestDeleteSite:
    """Tests for delete_site endpoint."""

    @pytest.mark.asyncio
    async def test_delete_site_not_found(self, mock_db_session, mock_admin_user):
        """Test deleting non-existent site."""
        from routers.sites import delete_site
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_site(uuid4(), mock_admin_user, mock_db_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_site_success(self, mock_db_session, mock_admin_user, sample_site):
        """Test successful site deletion."""
        from routers.sites import delete_site

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_site
        mock_db_session.execute.return_value = mock_result

        # This should not raise an exception
        await delete_site(sample_site.id, mock_admin_user, mock_db_session)

        # Verify delete was called (not awaited - this tests our fix)
        mock_db_session.delete.assert_called_once_with(sample_site)
        mock_db_session.commit.assert_called_once()
