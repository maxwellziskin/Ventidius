"""
Tests for edge device configuration module.
"""

import pytest
import os
import tempfile
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.config import (
    load_config,
    substitute_env_vars,
    process_dict_env_vars,
    CameraConfig,
    SiteConfig
)


class TestEnvVarSubstitution:
    """Tests for environment variable substitution."""

    def test_substitute_single_var(self):
        """Test substituting a single environment variable."""
        os.environ["TEST_VAR"] = "test_value"
        result = substitute_env_vars("prefix_${TEST_VAR}_suffix")
        assert result == "prefix_test_value_suffix"
        del os.environ["TEST_VAR"]

    def test_substitute_multiple_vars(self):
        """Test substituting multiple environment variables."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = substitute_env_vars("${VAR1}_${VAR2}")
        assert result == "value1_value2"
        del os.environ["VAR1"]
        del os.environ["VAR2"]

    def test_substitute_missing_var(self):
        """Test substituting a missing environment variable."""
        result = substitute_env_vars("${NONEXISTENT_VAR}")
        assert result == ""

    def test_no_substitution_needed(self):
        """Test string without environment variables."""
        result = substitute_env_vars("plain_string")
        assert result == "plain_string"

    def test_non_string_passthrough(self):
        """Test that non-string values pass through unchanged."""
        result = substitute_env_vars(123)
        assert result == 123


class TestProcessDictEnvVars:
    """Tests for recursive dictionary environment variable processing."""

    def test_process_nested_dict(self):
        """Test processing nested dictionaries."""
        os.environ["NESTED_VAR"] = "nested_value"
        input_dict = {
            "outer": {
                "inner": "${NESTED_VAR}"
            }
        }
        result = process_dict_env_vars(input_dict)
        assert result["outer"]["inner"] == "nested_value"
        del os.environ["NESTED_VAR"]

    def test_process_list_in_dict(self):
        """Test processing lists within dictionaries."""
        os.environ["LIST_VAR"] = "list_value"
        input_dict = {
            "items": ["${LIST_VAR}", "plain_string"]
        }
        result = process_dict_env_vars(input_dict)
        assert result["items"][0] == "list_value"
        assert result["items"][1] == "plain_string"
        del os.environ["LIST_VAR"]

    def test_process_non_string_values(self):
        """Test that non-string values are preserved."""
        input_dict = {
            "number": 42,
            "boolean": True,
            "null": None
        }
        result = process_dict_env_vars(input_dict)
        assert result["number"] == 42
        assert result["boolean"] is True
        assert result["null"] is None


class TestCameraConfig:
    """Tests for CameraConfig dataclass."""

    def test_rtsp_main_url(self):
        """Test RTSP main URL generation."""
        camera = CameraConfig(
            id="cam1",
            name="Test Camera",
            ip="192.168.1.100",
            rtsp_main="/Streaming/Channels/101",
            rtsp_sub="/Streaming/Channels/102",
            username="admin",
            password="secret"
        )
        expected = "rtsp://admin:secret@192.168.1.100/Streaming/Channels/101"
        assert camera.rtsp_main_url == expected

    def test_rtsp_sub_url(self):
        """Test RTSP sub URL generation."""
        camera = CameraConfig(
            id="cam1",
            name="Test Camera",
            ip="192.168.1.100",
            rtsp_main="/Streaming/Channels/101",
            rtsp_sub="/Streaming/Channels/102",
            username="admin",
            password="secret"
        )
        expected = "rtsp://admin:secret@192.168.1.100/Streaming/Channels/102"
        assert camera.rtsp_sub_url == expected

    def test_onvif_url(self):
        """Test ONVIF URL generation."""
        camera = CameraConfig(
            id="cam1",
            name="Test Camera",
            ip="192.168.1.100",
            rtsp_main="/Streaming/Channels/101",
            rtsp_sub="/Streaming/Channels/102",
            onvif_port=8080
        )
        expected = "http://192.168.1.100:8080/onvif/device_service"
        assert camera.onvif_url == expected


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_load_config_file_not_found(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_content = """
site_id: test-site
site_name: Test Site
cloud:
  api_endpoint: https://api.example.com
  wireguard_endpoint: wg.example.com:51820
  api_key: test-api-key
storage:
  path: /tmp/recordings
  retention_days: 30
mediamtx:
  rtsp_port: 8554
  hls_port: 8888
health:
  report_interval_seconds: 60
recording:
  segment_duration_minutes: 15
cameras:
  - id: cam1
    name: Front Door
    ip: 192.168.1.10
    rtsp_main: /stream1
    rtsp_sub: /stream2
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            config_path = f.name

        try:
            config = load_config(config_path)
            assert config.site_id == "test-site"
            assert config.site_name == "Test Site"
            assert config.cloud.api_endpoint == "https://api.example.com"
            assert len(config.cameras) == 1
            assert config.cameras[0].id == "cam1"
        finally:
            os.unlink(config_path)
