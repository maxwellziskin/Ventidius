"""
Ziskin Field Systems - Site Model

Represents surveillance sites with edge devices.
"""

import uuid
import secrets
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship

from db.database import Base


class Site(Base):
    """Site entity - represents a surveillance location."""

    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)

    # WireGuard configuration
    wireguard_pubkey = Column(String(44), nullable=True)
    wireguard_ip = Column(INET, nullable=True)

    # Edge device API key
    api_key = Column(String(64), default=lambda: secrets.token_urlsafe(48), unique=True)

    # Status tracking
    last_seen = Column(DateTime, nullable=True)
    status = Column(String(20), default="offline")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="sites")
    cameras = relationship("Camera", back_populates="site", cascade="all, delete-orphan")

    def to_dict(self, include_api_key: bool = False) -> dict:
        result = {
            "id": str(self.id),
            "client_id": str(self.client_id),
            "name": self.name,
            "address": self.address,
            "wireguard_ip": str(self.wireguard_ip) if self.wireguard_ip else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_api_key:
            result["api_key"] = self.api_key

        return result

    def update_status(self, online: bool):
        """Update site status based on health report."""
        self.status = "online" if online else "offline"
        if online:
            self.last_seen = datetime.utcnow()
