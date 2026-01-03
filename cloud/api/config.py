"""
Ziskin Field Systems - Cloud API Configuration

Application settings and environment configuration.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    API_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zfs"

    # Clerk Authentication
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_WEBHOOK_SECRET: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "alerts@zfs.example.com"

    # Storage
    UPLOAD_DIR: str = "/var/lib/zfs/uploads"
    MAX_EXPORT_SIZE_MB: int = 500

    # WireGuard
    WIREGUARD_INTERFACE: str = "wg0"
    WIREGUARD_PORT: int = 51820
    WIREGUARD_NETWORK: str = "10.100.0.0/24"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Stream URLs
    STREAM_TOKEN_EXPIRY: int = 3600  # 1 hour in seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
