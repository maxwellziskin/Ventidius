"""
Ziskin Field Systems - Health Reporter Module

Reports health status to cloud platform at regular intervals.
"""

import asyncio
import aiohttp
import structlog
from datetime import datetime
from typing import Callable, Optional
import platform
import psutil

from config import CloudConfig, HealthConfig

logger = structlog.get_logger(__name__)


class HealthReporter:
    """Reports health status to cloud platform."""

    def __init__(
        self,
        site_id: str,
        cloud_config: CloudConfig,
        health_config: HealthConfig
    ):
        self.site_id = site_id
        self.cloud_config = cloud_config
        self.health_config = health_config
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self, get_health_data: Callable):
        """Start health reporting loop."""
        logger.info(
            "Starting health reporter",
            interval=self.health_config.report_interval_seconds
        )

        self.running = True
        self._session = aiohttp.ClientSession()

        while self.running:
            try:
                # Collect health data
                app_health = await get_health_data()
                system_health = self._get_system_health()

                health_data = {
                    "site_id": self.site_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "system": system_health,
                    "application": app_health
                }

                # Report to cloud
                await self._report_health(health_data)

                await asyncio.sleep(self.health_config.report_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in health reporting", error=str(e))
                await asyncio.sleep(self.health_config.report_interval_seconds)

    async def stop(self):
        """Stop health reporting."""
        logger.info("Stopping health reporter")
        self.running = False

        if self._session:
            await self._session.close()
            self._session = None

    def _get_system_health(self) -> dict:
        """Collect system health metrics."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Get network stats
        net_io = psutil.net_io_counters()

        # Get temperature if available
        temps = {}
        try:
            temp_info = psutil.sensors_temperatures()
            if temp_info:
                for name, entries in temp_info.items():
                    if entries:
                        temps[name] = entries[0].current
        except Exception:
            pass

        # Get uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()

        return {
            "hostname": platform.node(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "uptime_seconds": int(uptime_seconds),
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_bytes": memory.total,
                "available_bytes": memory.available,
                "percent": memory.percent
            },
            "disk": {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
                "percent": disk.percent
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv
            },
            "temperatures": temps
        }

    async def _report_health(self, health_data: dict):
        """Send health data to cloud API."""
        if not self._session:
            return

        url = f"{self.cloud_config.api_endpoint}/api/edge/health"

        try:
            async with self._session.post(
                url,
                json=health_data,
                headers={
                    "Authorization": f"Bearer {self.cloud_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.debug("Health report sent successfully")
                else:
                    logger.warning(
                        "Health report failed",
                        status=response.status,
                        response=await response.text()
                    )

        except aiohttp.ClientError as e:
            logger.warning("Failed to send health report", error=str(e))
        except Exception as e:
            logger.error("Unexpected error sending health report", error=str(e))

    async def send_alert(self, alert_type: str, message: str, details: dict = None):
        """Send an alert to the cloud platform."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        url = f"{self.cloud_config.api_endpoint}/api/edge/alert"

        alert_data = {
            "site_id": self.site_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": alert_type,
            "message": message,
            "details": details or {}
        }

        try:
            async with self._session.post(
                url,
                json=alert_data,
                headers={
                    "Authorization": f"Bearer {self.cloud_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info("Alert sent", alert_type=alert_type)
                else:
                    logger.warning(
                        "Failed to send alert",
                        status=response.status
                    )

        except Exception as e:
            logger.error("Error sending alert", error=str(e))
