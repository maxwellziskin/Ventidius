"""
Ziskin Field Systems - Export Schemas
"""

from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class ExportCreate(BaseModel):
    """Schema for creating an export request."""
    camera_id: UUID
    start_time: datetime
    end_time: datetime

    @validator("end_time")
    def validate_time_range(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("end_time must be after start_time")

        # Check max duration (few hours)
        if "start_time" in values:
            duration = (v - values["start_time"]).total_seconds()
            max_duration = 4 * 60 * 60  # 4 hours
            if duration > max_duration:
                raise ValueError("Export duration cannot exceed 4 hours")

        return v


class ExportResponse(BaseModel):
    """Schema for export response."""
    id: UUID
    camera_id: UUID
    requested_by: UUID
    start_time: datetime
    end_time: datetime
    status: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExportStatusUpdate(BaseModel):
    """Schema for updating export status (from edge device)."""
    status: str
    file_size: Optional[int] = None
    error_message: Optional[str] = None
