"""
Ziskin Field Systems - Site Schemas
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class SiteCreate(BaseModel):
    """Schema for creating a site."""
    client_id: UUID
    name: str
    address: Optional[str] = None


class SiteUpdate(BaseModel):
    """Schema for updating a site."""
    name: Optional[str] = None
    address: Optional[str] = None
    wireguard_pubkey: Optional[str] = None


class SiteResponse(BaseModel):
    """Schema for site response."""
    id: UUID
    client_id: UUID
    name: str
    address: Optional[str] = None
    wireguard_ip: Optional[str] = None
    last_seen: Optional[datetime] = None
    status: str
    created_at: datetime
    api_key: Optional[str] = None  # Only included for admins

    class Config:
        from_attributes = True


class SiteHealth(BaseModel):
    """Schema for site health report from edge device."""
    site_id: str
    timestamp: datetime
    system: dict
    application: dict


class CameraStatus(BaseModel):
    """Camera status within health report."""
    camera_id: str
    online: bool
    last_seen: Optional[datetime] = None
    error_message: Optional[str] = None
