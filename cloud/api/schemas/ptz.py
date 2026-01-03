"""
Ziskin Field Systems - PTZ Schemas
"""

from pydantic import BaseModel, validator
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


class PTZCommand(BaseModel):
    """Schema for PTZ control command."""
    action: Literal["move", "stop", "preset"]
    pan: Optional[float] = None
    tilt: Optional[float] = None
    zoom: Optional[float] = None
    preset_id: Optional[int] = None

    @validator("pan", "tilt", "zoom")
    def validate_range(cls, v):
        if v is not None and (v < -1 or v > 1):
            raise ValueError("Value must be between -1 and 1")
        return v


class PTZPresetCreate(BaseModel):
    """Schema for creating a PTZ preset."""
    name: str


class PTZPresetResponse(BaseModel):
    """Schema for PTZ preset response."""
    id: UUID
    camera_id: UUID
    name: str
    pan: Optional[float] = None
    tilt: Optional[float] = None
    zoom: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True
