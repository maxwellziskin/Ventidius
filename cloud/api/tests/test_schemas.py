"""
Tests for Pydantic schema validation.

These tests verify schema definitions work correctly.
"""

import pytest
from pydantic import BaseModel, ValidationError
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime


# Define test schemas that mirror the actual API schemas
class SiteCreateSchema(BaseModel):
    """Schema for creating a site."""
    client_id: UUID
    name: str
    address: Optional[str] = None


class SiteUpdateSchema(BaseModel):
    """Schema for updating a site."""
    name: Optional[str] = None
    address: Optional[str] = None
    wireguard_pubkey: Optional[str] = None


class CameraCreateSchema(BaseModel):
    """Schema for creating a camera."""
    site_id: UUID
    name: str
    local_ip: str
    rtsp_path: str
    onvif_port: Optional[int] = 80
    onvif_user: Optional[str] = None
    onvif_pass: Optional[str] = None
    is_ptz: bool = False


class ClientCreateSchema(BaseModel):
    """Schema for creating a client."""
    name: str
    contact_email: str


class ExportCreateSchema(BaseModel):
    """Schema for creating an export request."""
    camera_id: UUID
    start_time: datetime
    end_time: datetime


class TestSiteSchemas:
    """Tests for site schemas."""

    def test_site_create_valid(self):
        """Test valid site creation schema."""
        data = {
            "client_id": str(uuid4()),
            "name": "Test Site",
            "address": "123 Test St"
        }
        schema = SiteCreateSchema(**data)
        assert schema.name == "Test Site"
        assert schema.address == "123 Test St"

    def test_site_create_minimal(self):
        """Test minimal site creation (optional fields omitted)."""
        data = {
            "client_id": str(uuid4()),
            "name": "Test Site"
        }
        schema = SiteCreateSchema(**data)
        assert schema.name == "Test Site"
        assert schema.address is None

    def test_site_create_missing_required(self):
        """Test site creation with missing required fields."""
        with pytest.raises(ValidationError):
            SiteCreateSchema(name="Test Site")  # Missing client_id

    def test_site_update_partial(self):
        """Test partial site update."""
        schema = SiteUpdateSchema(name="New Name")
        assert schema.name == "New Name"
        assert schema.address is None


class TestCameraSchemas:
    """Tests for camera schemas."""

    def test_camera_create_valid(self):
        """Test valid camera creation schema."""
        data = {
            "site_id": str(uuid4()),
            "name": "Front Door",
            "local_ip": "192.168.1.100",
            "rtsp_path": "/stream1"
        }
        schema = CameraCreateSchema(**data)
        assert schema.name == "Front Door"
        assert schema.local_ip == "192.168.1.100"
        assert schema.is_ptz is False  # Default

    def test_camera_create_with_ptz(self):
        """Test camera creation with PTZ enabled."""
        data = {
            "site_id": str(uuid4()),
            "name": "PTZ Camera",
            "local_ip": "192.168.1.101",
            "rtsp_path": "/stream1",
            "is_ptz": True,
            "onvif_port": 8080
        }
        schema = CameraCreateSchema(**data)
        assert schema.is_ptz is True
        assert schema.onvif_port == 8080

    def test_camera_create_missing_required(self):
        """Test camera creation with missing required fields."""
        with pytest.raises(ValidationError):
            CameraCreateSchema(
                site_id=str(uuid4()),
                name="Camera"
                # Missing local_ip and rtsp_path
            )


class TestClientSchemas:
    """Tests for client schemas."""

    def test_client_create_valid(self):
        """Test valid client creation schema."""
        schema = ClientCreateSchema(
            name="Test Client",
            contact_email="test@example.com"
        )
        assert schema.name == "Test Client"
        assert schema.contact_email == "test@example.com"

    def test_client_create_missing_email(self):
        """Test client creation with missing email."""
        with pytest.raises(ValidationError):
            ClientCreateSchema(name="Test Client")


class TestExportSchemas:
    """Tests for export schemas."""

    def test_export_create_valid(self):
        """Test valid export creation schema."""
        now = datetime.utcnow()
        schema = ExportCreateSchema(
            camera_id=uuid4(),
            start_time=now,
            end_time=now
        )
        assert schema.start_time == now
        assert schema.end_time == now

    def test_export_create_with_string_dates(self):
        """Test export creation with ISO format date strings."""
        schema = ExportCreateSchema(
            camera_id=str(uuid4()),
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T11:00:00"
        )
        assert schema.start_time.hour == 10
        assert schema.end_time.hour == 11
