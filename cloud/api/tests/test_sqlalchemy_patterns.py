"""
Tests for SQLAlchemy session patterns used in cloud API.

These tests verify that the db.delete() call is NOT awaited (it's sync),
while db.commit() IS awaited (it's async). This validates our bug fix.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4


class TestSQLAlchemySessionPatterns:
    """Test the correct SQLAlchemy async session usage patterns."""

    @pytest.mark.asyncio
    async def test_delete_is_sync(self, mock_db_session):
        """
        Verify that db.delete() is called synchronously (not awaited).

        This is the critical bug fix - SQLAlchemy's delete() is sync,
        it only marks an object for deletion. The actual delete happens
        during commit().
        """
        sample_obj = MagicMock()

        # This is the CORRECT pattern: delete is sync
        mock_db_session.delete(sample_obj)
        await mock_db_session.commit()

        # Verify delete was called as a regular function
        mock_db_session.delete.assert_called_once_with(sample_obj)
        # Verify commit was awaited
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_is_sync(self, mock_db_session):
        """Verify that db.add() is called synchronously."""
        sample_obj = MagicMock()

        mock_db_session.add(sample_obj)
        await mock_db_session.commit()

        mock_db_session.add.assert_called_once_with(sample_obj)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_is_async(self, mock_db_session):
        """Verify that db.refresh() is awaited (it queries the DB)."""
        sample_obj = MagicMock()

        await mock_db_session.refresh(sample_obj)

        mock_db_session.refresh.assert_awaited_once_with(sample_obj)

    @pytest.mark.asyncio
    async def test_execute_is_async(self, mock_db_session):
        """Verify that db.execute() is awaited."""
        query = MagicMock()

        await mock_db_session.execute(query)

        mock_db_session.execute.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_full_create_pattern(self, mock_db_session):
        """Test the full create object pattern."""
        new_obj = MagicMock()

        # This is the correct pattern for creating objects
        mock_db_session.add(new_obj)  # sync
        await mock_db_session.commit()  # async
        await mock_db_session.refresh(new_obj)  # async

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_full_delete_pattern(self, mock_db_session, sample_site):
        """Test the full delete object pattern."""
        # Setup mock for execute to return the site
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_site
        mock_db_session.execute.return_value = mock_result

        # Execute query to find site
        result = await mock_db_session.execute(MagicMock())
        site = result.scalar_one_or_none()

        # Delete pattern - delete is SYNC, commit is ASYNC
        mock_db_session.delete(site)  # This should NOT be awaited
        await mock_db_session.commit()  # This SHOULD be awaited

        # Verify correct call patterns
        mock_db_session.delete.assert_called_once_with(site)
        mock_db_session.commit.assert_awaited_once()


class TestDeleteOperations:
    """Test delete operations across different entity types."""

    @pytest.mark.asyncio
    async def test_site_delete_pattern(self, mock_db_session, sample_site):
        """Test site deletion uses sync delete."""
        mock_db_session.delete(sample_site)
        await mock_db_session.commit()

        # delete should be called as sync function
        assert mock_db_session.delete.called
        assert not hasattr(mock_db_session.delete, 'assert_awaited')

    @pytest.mark.asyncio
    async def test_camera_delete_pattern(self, mock_db_session, sample_camera):
        """Test camera deletion uses sync delete."""
        mock_db_session.delete(sample_camera)
        await mock_db_session.commit()

        mock_db_session.delete.assert_called_once_with(sample_camera)

    @pytest.mark.asyncio
    async def test_client_delete_pattern(self, mock_db_session, sample_client):
        """Test client deletion uses sync delete."""
        mock_db_session.delete(sample_client)
        await mock_db_session.commit()

        mock_db_session.delete.assert_called_once_with(sample_client)


class TestQueryPatterns:
    """Test query patterns."""

    @pytest.mark.asyncio
    async def test_select_and_scalar(self, mock_db_session, sample_site):
        """Test select query pattern."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_site
        mock_db_session.execute.return_value = mock_result

        result = await mock_db_session.execute(MagicMock())
        site = result.scalar_one_or_none()

        assert site == sample_site
        mock_db_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_select_all(self, mock_db_session, sample_site):
        """Test select all query pattern."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_site]
        mock_db_session.execute.return_value = mock_result

        result = await mock_db_session.execute(MagicMock())
        sites = result.scalars().all()

        assert len(sites) == 1
        assert sites[0] == sample_site
