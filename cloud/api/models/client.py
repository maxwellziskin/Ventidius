"""
Ziskin Field Systems - Client Model

Represents investigation clients who own sites.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.database import Base


class Client(Base):
    """Client entity - represents an investigation client."""

    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sites = relationship("Site", back_populates="client", cascade="all, delete-orphan")
    users = relationship("User", back_populates="client")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "contact_email": self.contact_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
