"""
Ziskin Field Systems - User Model

Represents system users with role-based access control.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.database import Base


class User(Base):
    """User entity - represents a system user."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(20), default="client")  # admin, client
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)

    # Session management
    session_limit = Column(Integer, default=0)  # 0 = unlimited

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="users")
    camera_access = relationship("UserCameraAccess", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    export_requests = relationship("ExportRequest", back_populates="requested_by_user")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "clerk_id": self.clerk_id,
            "email": self.email,
            "role": self.role,
            "client_id": str(self.client_id) if self.client_id else None,
            "session_limit": self.session_limit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserCameraAccess(Base):
    """User Camera Access entity - defines per-camera permissions."""

    __tablename__ = "user_camera_access"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), primary_key=True)

    can_view = Column(Boolean, default=True)
    can_ptz = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="camera_access")
    camera = relationship("Camera", back_populates="user_access")

    def to_dict(self) -> dict:
        return {
            "user_id": str(self.user_id),
            "camera_id": str(self.camera_id),
            "can_view": self.can_view,
            "can_ptz": self.can_ptz,
        }
