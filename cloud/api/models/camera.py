"""
Ziskin Field Systems - Camera Model

Represents surveillance cameras at sites.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship

from db.database import Base


class Camera(Base):
    """Camera entity - represents a surveillance camera."""

    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Network configuration
    local_ip = Column(INET, nullable=True)
    rtsp_path = Column(String(255), nullable=True)
    onvif_port = Column(Integer, default=80)
    onvif_user = Column(String(255), nullable=True)
    onvif_pass = Column(String(255), nullable=True)  # Encrypted in database

    # Camera capabilities
    is_ptz = Column(Boolean, default=False)

    # Status tracking
    status = Column(String(20), default="offline")
    last_seen = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    site = relationship("Site", back_populates="cameras")
    presets = relationship("PTZPreset", back_populates="camera", cascade="all, delete-orphan")
    user_access = relationship("UserCameraAccess", back_populates="camera", cascade="all, delete-orphan")
    export_requests = relationship("ExportRequest", back_populates="camera")

    def to_dict(self, include_credentials: bool = False) -> dict:
        result = {
            "id": str(self.id),
            "site_id": str(self.site_id),
            "name": self.name,
            "local_ip": str(self.local_ip) if self.local_ip else None,
            "rtsp_path": self.rtsp_path,
            "onvif_port": self.onvif_port,
            "is_ptz": self.is_ptz,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_credentials:
            result["onvif_user"] = self.onvif_user
            result["onvif_pass"] = self.onvif_pass

        return result

    def update_status(self, online: bool):
        """Update camera status."""
        self.status = "online" if online else "offline"
        if online:
            self.last_seen = datetime.utcnow()


class PTZPreset(Base):
    """PTZ Preset entity - represents a saved camera position."""

    __tablename__ = "ptz_presets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Position coordinates
    pan = Column(Float, nullable=True)
    tilt = Column(Float, nullable=True)
    zoom = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    camera = relationship("Camera", back_populates="presets")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "camera_id": str(self.camera_id),
            "name": self.name,
            "pan": self.pan,
            "tilt": self.tilt,
            "zoom": self.zoom,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
