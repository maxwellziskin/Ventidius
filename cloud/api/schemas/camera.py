"""
Ziskin Field Systems - Camera Schemas
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class CameraCreate(BaseModel):
    """Schema for creating a camera."""
    site_id: UUID
    name: str
    local_ip: Optional[str] = None
    rtsp_path: Optional[str] = "/Streaming/Channels/101"
    onvif_port: int = 80
    onvif_user: Optional[str] = None
    onvif_pass: Optional[str] = None
    is_ptz: bool = False


class CameraUpdate(BaseModel):
    """Schema for updating a camera."""
    name: Optional[str] = None
    local_ip: Optional[str] = None
    rtsp_path: Optional[str] = None
    onvif_port: Optional[int] = None
    onvif_user: Optional[str] = None
    onvif_pass: Optional[str] = None
    is_ptz: Optional[bool] = None


class CameraResponse(BaseModel):
    """Schema for camera response."""
    id: UUID
    site_id: UUID
    name: str
    local_ip: Optional[str] = None
    rtsp_path: Optional[str] = None
    onvif_port: int
    is_ptz: bool
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CameraStreamUrl(BaseModel):
    """Schema for stream URL response."""
    camera_id: UUID
    hls_url: str
    expires_at: datetime
