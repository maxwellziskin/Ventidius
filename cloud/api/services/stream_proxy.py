"""
Ziskin Field Systems - Stream Proxy Service

Handles HLS stream proxying from edge devices to clients.
"""

import asyncio
import aiohttp
import structlog
from typing import Optional
from datetime import datetime
import hashlib

from config import settings

logger = structlog.get_logger(__name__)


class StreamProxy:
    """Proxies HLS streams from edge devices to authenticated clients."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache = {}  # Simple in-memory cache for segments

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def verify_token(self, camera_id: str, token: str, expires: int) -> bool:
        """Verify stream access token."""
        now = datetime.utcnow().timestamp()

        if expires < now:
            return False

        expected_data = f"{camera_id}:{expires}:{settings.SECRET_KEY}"
        expected_token = hashlib.sha256(expected_data.encode()).hexdigest()[:32]

        return token == expected_token

    async def get_manifest(
        self,
        site_wireguard_ip: str,
        camera_id: str
    ) -> Optional[bytes]:
        """Fetch HLS manifest from edge device."""
        session = await self.get_session()

        # Edge device runs MediaMTX on port 8888
        url = f"http://{site_wireguard_ip}:8888/{camera_id}/index.m3u8"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.warning(
                        "Failed to fetch manifest",
                        url=url,
                        status=response.status
                    )
                    return None

        except Exception as e:
            logger.error("Error fetching manifest", url=url, error=str(e))
            return None

    async def get_segment(
        self,
        site_wireguard_ip: str,
        camera_id: str,
        segment_name: str
    ) -> Optional[bytes]:
        """Fetch HLS segment from edge device."""
        cache_key = f"{site_wireguard_ip}:{camera_id}:{segment_name}"

        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Cache for 30 seconds
            if (datetime.utcnow().timestamp() - cached["time"]) < 30:
                return cached["data"]

        session = await self.get_session()
        url = f"http://{site_wireguard_ip}:8888/{camera_id}/{segment_name}"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.read()

                    # Cache the segment
                    self._cache[cache_key] = {
                        "data": data,
                        "time": datetime.utcnow().timestamp()
                    }

                    # Clean old cache entries
                    await self._cleanup_cache()

                    return data
                else:
                    logger.warning(
                        "Failed to fetch segment",
                        url=url,
                        status=response.status
                    )
                    return None

        except Exception as e:
            logger.error("Error fetching segment", url=url, error=str(e))
            return None

    async def _cleanup_cache(self):
        """Remove old cache entries."""
        now = datetime.utcnow().timestamp()
        expired_keys = [
            key for key, value in self._cache.items()
            if (now - value["time"]) > 60
        ]
        for key in expired_keys:
            del self._cache[key]


# Global stream proxy instance
stream_proxy = StreamProxy()
