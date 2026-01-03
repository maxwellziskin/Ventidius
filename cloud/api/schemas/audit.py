"""
Ziskin Field Systems - Audit Schemas
"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from uuid import UUID


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: UUID
    user_id: Optional[UUID] = None
    camera_id: Optional[UUID] = None
    action: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogCreate(BaseModel):
    """Schema for creating audit log entry (internal use)."""
    user_id: Optional[UUID] = None
    camera_id: Optional[UUID] = None
    action: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
