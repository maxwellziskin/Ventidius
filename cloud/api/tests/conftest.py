"""
Pytest fixtures for cloud API tests.

These tests are designed to be isolated unit tests that don't require
database connections or external dependencies.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """Create a mock database session that mimics SQLAlchemy AsyncSession behavior."""
    session = MagicMock()
    # Async methods
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # Sync methods (important: these should NOT be async)
    session.add = MagicMock()
    session.delete = MagicMock()  # This is sync in SQLAlchemy!
    return session


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "admin@example.com"
    user.role = "admin"
    user.is_admin = True
    user.client_id = None
    return user


@pytest.fixture
def mock_client_user():
    """Create a mock client user."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "client@example.com"
    user.role = "client"
    user.is_admin = False
    user.client_id = uuid4()
    return user


@pytest.fixture
def sample_site():
    """Create a sample site object."""
    site = MagicMock()
    site.id = uuid4()
    site.name = "Test Site"
    site.address = "123 Test St"
    site.client_id = uuid4()
    site.status = "online"
    site.last_seen = datetime.utcnow()
    site.created_at = datetime.utcnow()
    site.to_dict = MagicMock(return_value={
        "id": str(site.id),
        "name": "Test Site",
        "address": "123 Test St",
        "status": "online"
    })
    return site


@pytest.fixture
def sample_camera():
    """Create a sample camera object."""
    camera = MagicMock()
    camera.id = uuid4()
    camera.site_id = uuid4()
    camera.name = "Front Door Camera"
    camera.local_ip = "192.168.1.100"
    camera.rtsp_path = "/stream1"
    camera.is_ptz = False
    camera.status = "online"
    camera.to_dict = MagicMock(return_value={
        "id": str(camera.id),
        "name": "Front Door Camera",
        "status": "online"
    })
    return camera


@pytest.fixture
def sample_client():
    """Create a sample client object."""
    client = MagicMock()
    client.id = uuid4()
    client.name = "Test Client"
    client.contact_email = "contact@example.com"
    client.created_at = datetime.utcnow()
    client.to_dict = MagicMock(return_value={
        "id": str(client.id),
        "name": "Test Client",
        "contact_email": "contact@example.com"
    })
    return client
