"""
Ziskin Field Systems - Edge Device Configuration Module

Handles loading and validation of YAML configuration with environment variable substitution.
"""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class CloudConfig:
    api_endpoint: str
    wireguard_endpoint: str
    api_key: str = ""


@dataclass
class StorageConfig:
    path: str = "/mnt/recordings"
    retention_days: int = 90
    max_usage_percent: int = 90


@dataclass
class MediaMTXConfig:
    rtsp_port: int = 8554
    hls_port: int = 8888
    config_path: str = "/opt/ziskin/mediamtx.yml"


@dataclass
class HealthConfig:
    report_interval_seconds: int = 30
    camera_check_interval_seconds: int = 60


@dataclass
class RecordingConfig:
    segment_duration_minutes: int = 30
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    timestamp_position: str = "top-left"
    timestamp_font_size: int = 24


@dataclass
class CameraConfig:
    id: str
    name: str
    ip: str
    rtsp_main: str
    rtsp_sub: str
    onvif_port: int = 80
    username: str = "admin"
    password: str = ""
    ptz: bool = False

    @property
    def rtsp_main_url(self) -> str:
        """Get full RTSP URL for main stream."""
        return f"rtsp://{self.username}:{self.password}@{self.ip}{self.rtsp_main}"

    @property
    def rtsp_sub_url(self) -> str:
        """Get full RTSP URL for sub stream."""
        return f"rtsp://{self.username}:{self.password}@{self.ip}{self.rtsp_sub}"

    @property
    def onvif_url(self) -> str:
        """Get ONVIF service URL."""
        return f"http://{self.ip}:{self.onvif_port}/onvif/device_service"


@dataclass
class SiteConfig:
    site_id: str
    site_name: str
    cloud: CloudConfig
    storage: StorageConfig
    mediamtx: MediaMTXConfig
    health: HealthConfig
    recording: RecordingConfig
    cameras: List[CameraConfig] = field(default_factory=list)


def substitute_env_vars(value: str) -> str:
    """Substitute environment variables in format ${VAR_NAME}."""
    pattern = r'\$\{([^}]+)\}'

    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    if isinstance(value, str):
        return re.sub(pattern, replacer, value)
    return value


def process_dict_env_vars(d: dict) -> dict:
    """Recursively process dictionary to substitute environment variables."""
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = process_dict_env_vars(value)
        elif isinstance(value, list):
            result[key] = [
                process_dict_env_vars(item) if isinstance(item, dict)
                else substitute_env_vars(item) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = substitute_env_vars(value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "/opt/ziskin/config.yaml") -> SiteConfig:
    """Load and parse configuration from YAML file."""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(path, 'r') as f:
        raw_config = yaml.safe_load(f)

    # Substitute environment variables
    config = process_dict_env_vars(raw_config)

    # Parse cloud config
    cloud_data = config.get('cloud', {})
    cloud = CloudConfig(
        api_endpoint=cloud_data.get('api_endpoint', ''),
        wireguard_endpoint=cloud_data.get('wireguard_endpoint', ''),
        api_key=cloud_data.get('api_key', '')
    )

    # Parse storage config
    storage_data = config.get('storage', {})
    storage = StorageConfig(
        path=storage_data.get('path', '/mnt/recordings'),
        retention_days=storage_data.get('retention_days', 90),
        max_usage_percent=storage_data.get('max_usage_percent', 90)
    )

    # Parse MediaMTX config
    mediamtx_data = config.get('mediamtx', {})
    mediamtx = MediaMTXConfig(
        rtsp_port=mediamtx_data.get('rtsp_port', 8554),
        hls_port=mediamtx_data.get('hls_port', 8888),
        config_path=mediamtx_data.get('config_path', '/opt/ziskin/mediamtx.yml')
    )

    # Parse health config
    health_data = config.get('health', {})
    health = HealthConfig(
        report_interval_seconds=health_data.get('report_interval_seconds', 30),
        camera_check_interval_seconds=health_data.get('camera_check_interval_seconds', 60)
    )

    # Parse recording config
    recording_data = config.get('recording', {})
    recording = RecordingConfig(
        segment_duration_minutes=recording_data.get('segment_duration_minutes', 30),
        timestamp_format=recording_data.get('timestamp_format', '%Y-%m-%d %H:%M:%S'),
        timestamp_position=recording_data.get('timestamp_position', 'top-left'),
        timestamp_font_size=recording_data.get('timestamp_font_size', 24)
    )

    # Parse cameras
    cameras = []
    for cam_data in config.get('cameras', []):
        camera = CameraConfig(
            id=cam_data['id'],
            name=cam_data['name'],
            ip=cam_data['ip'],
            rtsp_main=cam_data.get('rtsp_main', '/Streaming/Channels/101'),
            rtsp_sub=cam_data.get('rtsp_sub', '/Streaming/Channels/102'),
            onvif_port=cam_data.get('onvif_port', 80),
            username=cam_data.get('username', 'admin'),
            password=cam_data.get('password', ''),
            ptz=cam_data.get('ptz', False)
        )
        cameras.append(camera)

    return SiteConfig(
        site_id=config.get('site_id', ''),
        site_name=config.get('site_name', ''),
        cloud=cloud,
        storage=storage,
        mediamtx=mediamtx,
        health=health,
        recording=recording,
        cameras=cameras
    )
