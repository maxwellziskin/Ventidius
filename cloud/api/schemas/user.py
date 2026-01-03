"""
Ziskin Field Systems - User Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    """Schema for creating a user (internal use)."""
    clerk_id: str
    email: EmailStr
    role: str = "client"
    client_id: Optional[UUID] = None
    session_limit: int = 0


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    role: Optional[str] = None
    client_id: Optional[UUID] = None
    session_limit: Optional[int] = None


class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    clerk_id: str
    email: str
    role: str
    client_id: Optional[UUID] = None
    session_limit: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserInvite(BaseModel):
    """Schema for inviting a new user."""
    email: EmailStr
    role: str = "client"
    client_id: Optional[UUID] = None
    camera_ids: Optional[List[UUID]] = None


class CameraPermission(BaseModel):
    """Schema for camera permission."""
    camera_id: UUID
    can_view: bool = True
    can_ptz: bool = False


class UserCameraPermissions(BaseModel):
    """Schema for updating user camera permissions."""
    permissions: List[CameraPermission]
