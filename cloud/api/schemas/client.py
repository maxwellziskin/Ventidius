"""
Ziskin Field Systems - Client Schemas
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


class ClientCreate(BaseModel):
    """Schema for creating a client."""
    name: str
    contact_email: Optional[EmailStr] = None


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    name: Optional[str] = None
    contact_email: Optional[EmailStr] = None


class ClientResponse(BaseModel):
    """Schema for client response."""
    id: UUID
    name: str
    contact_email: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
