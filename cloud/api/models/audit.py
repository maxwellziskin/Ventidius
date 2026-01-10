"""
Ziskin Field Systems - Audit and Export Models

Audit logging and export request tracking.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship

from db.database import Base


class AuditLog(Base):
    """Audit Log entity - immutable record of user actions."""

    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=True)

    action = Column(String(50), nullable=False)
    details = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "camera_id": str(self.camera_id) if self.camera_id else None,
            "action": self.action,
            "details": self.details,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class ExportRequest(Base):
    """Export Request entity - tracks video clip export requests."""

    __tablename__ = "export_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Time range for export
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

    # Status tracking
    status = Column(String(20), default="pending")  # pending, processing, uploading, completed, failed

    # File information
    file_url = Column(Text, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    camera = relationship("Camera", back_populates="export_requests")
    requested_by_user = relationship("User", back_populates="export_requests")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "camera_id": str(self.camera_id),
            "requested_by": str(self.requested_by),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "file_url": self.file_url,
            "file_size": self.file_size,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def mark_completed(self, file_url: str, file_size: int):
        """Mark export as completed."""
        self.status = "completed"
        self.file_url = file_url
        self.file_size = file_size
        self.completed_at = datetime.utcnow()

    def mark_failed(self, error_message: str):
        """Mark export as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
