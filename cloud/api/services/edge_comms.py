"""
Ziskin Field Systems - Edge Communications Service

Manages communication with edge devices via WireGuard.
"""

import asyncio
import subprocess
import structlog
from typing import Optional, Dict
from datetime import datetime
import ipaddress

from config import settings

logger = structlog.get_logger(__name__)


class EdgeCommunications:
    """Manages edge device communications and WireGuard configuration."""

    def __init__(self):
        self.network = ipaddress.ip_network(settings.WIREGUARD_NETWORK)
        self._next_ip = 2  # Start at .2 (.1 is server)

    def generate_wireguard_config(
        self,
        site_id: str,
        site_pubkey: str
    ) -> Dict[str, str]:
        """
        Generate WireGuard configuration for a new edge device.

        Returns server-side peer config and client config.
        """
        # Allocate IP address
        client_ip = self._allocate_ip()

        if not client_ip:
            raise RuntimeError("No available IP addresses in WireGuard network")

        # Server peer configuration
        server_peer_config = f"""
# Site: {site_id}
[Peer]
PublicKey = {site_pubkey}
AllowedIPs = {client_ip}/32
"""

        # Client configuration template
        client_config = f"""
[Interface]
PrivateKey = <PRIVATE_KEY>
Address = {client_ip}/24

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = {settings.WIREGUARD_ENDPOINT}:{settings.WIREGUARD_PORT}
AllowedIPs = {settings.WIREGUARD_NETWORK}
PersistentKeepalive = 25
"""

        return {
            "client_ip": str(client_ip),
            "server_peer_config": server_peer_config,
            "client_config_template": client_config
        }

    def _allocate_ip(self) -> Optional[ipaddress.IPv4Address]:
        """Allocate the next available IP address."""
        hosts = list(self.network.hosts())

        if self._next_ip >= len(hosts):
            return None

        ip = hosts[self._next_ip]
        self._next_ip += 1
        return ip

    async def add_peer(self, pubkey: str, allowed_ip: str) -> bool:
        """Add a WireGuard peer dynamically."""
        try:
            cmd = [
                "wg", "set", settings.WIREGUARD_INTERFACE,
                "peer", pubkey,
                "allowed-ips", f"{allowed_ip}/32"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(
                    "Failed to add WireGuard peer",
                    pubkey=pubkey[:20] + "...",
                    error=stderr.decode()
                )
                return False

            logger.info("WireGuard peer added", allowed_ip=allowed_ip)
            return True

        except Exception as e:
            logger.error("Error adding WireGuard peer", error=str(e))
            return False

    async def remove_peer(self, pubkey: str) -> bool:
        """Remove a WireGuard peer."""
        try:
            cmd = [
                "wg", "set", settings.WIREGUARD_INTERFACE,
                "peer", pubkey,
                "remove"
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if process.returncode != 0:
                return False

            logger.info("WireGuard peer removed", pubkey=pubkey[:20] + "...")
            return True

        except Exception as e:
            logger.error("Error removing WireGuard peer", error=str(e))
            return False

    async def get_peer_status(self) -> Dict[str, dict]:
        """Get status of all WireGuard peers."""
        try:
            cmd = ["wg", "show", settings.WIREGUARD_INTERFACE, "dump"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {}

            peers = {}
            lines = stdout.decode().strip().split('\n')

            # Skip first line (interface info)
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) >= 5:
                    pubkey = parts[0]
                    endpoint = parts[2] if parts[2] != "(none)" else None
                    allowed_ips = parts[3]
                    last_handshake = int(parts[4]) if parts[4] != "0" else None
                    rx_bytes = int(parts[5]) if len(parts) > 5 else 0
                    tx_bytes = int(parts[6]) if len(parts) > 6 else 0

                    peers[pubkey] = {
                        "endpoint": endpoint,
                        "allowed_ips": allowed_ips,
                        "last_handshake": datetime.fromtimestamp(last_handshake).isoformat() if last_handshake else None,
                        "rx_bytes": rx_bytes,
                        "tx_bytes": tx_bytes,
                        "online": last_handshake is not None and (datetime.now().timestamp() - last_handshake) < 180
                    }

            return peers

        except Exception as e:
            logger.error("Error getting WireGuard status", error=str(e))
            return {}

    async def ping_edge(self, ip: str) -> bool:
        """Ping an edge device to check connectivity."""
        try:
            cmd = ["ping", "-c", "1", "-W", "2", ip]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            return process.returncode == 0

        except Exception as e:
            logger.error("Error pinging edge device", ip=ip, error=str(e))
            return False


# Global edge communications instance
edge_comms = EdgeCommunications()
