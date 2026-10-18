"""Global test configuration and fixtures for Home Assistant Portainer integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.config_entries import ConfigEntry

from custom_components.portainer.const import DOMAIN


@pytest.fixture
def config_entry():
    """Create a mock config entry for Portainer."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Portainer",
        data={
            "host": "http://localhost:9000",
            "username": "test_user",
            "password": "test_password",
            "verify_ssl": False,
        },
        source="user",
        unique_id="test-portainer",
    )


@pytest.fixture
def mock_portainer_api():
    """Mock Portainer API responses."""
    mock_api = MagicMock()

    # Mock container data
    mock_api.get_containers.return_value = [
        {
            "Id": "container1",
            "Names": ["/test-container"],
            "State": "running",
            "Status": "Up 2 hours",
            "Image": "nginx:latest",
        },
        {
            "Id": "container2",
            "Names": ["/stopped-container"],
            "State": "exited",
            "Status": "Exited (0) 1 hour ago",
            "Image": "redis:latest",
        },
    ]

    # Mock endpoint data
    mock_api.get_endpoints.return_value = [
        {
            "Id": 1,
            "Name": "local",
            "Type": 1,
            "URL": "unix:///var/run/docker.sock",
        }
    ]

    # Mock system info
    mock_api.get_system_info.return_value = {
        "version": "2.18.0",
        "platform": "linux",
    }

    return mock_api


@pytest.fixture
def mock_config_flow():
    """Mock config flow for testing."""
    return MagicMock()


@pytest.fixture
def mock_coordinator():
    """Mock data coordinator for testing."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {}
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_hass_config():
    """Mock Home Assistant configuration."""
    return {
        "latitude": 32.87336,
        "longitude": -117.22743,
        "elevation": 0,
        "time_zone": "UTC",
        "units": "metric",
    }


@pytest.fixture
def mock_websocket():
    """Mock WebSocket for testing."""
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    return websocket


@pytest.fixture
def capture_logs(caplog):
    """Capture logs during test execution."""
    return caplog


@pytest.fixture
def mock_timer():
    """Mock timer for testing scheduled updates."""
    timer = MagicMock()
    timer.cancel = MagicMock()
    return timer


@pytest.fixture
def sample_portainer_config():
    """Sample Portainer configuration for testing."""
    return {
        "host": "http://localhost:9000",
        "username": "test_user",
        "password": "test_password",
        "verify_ssl": False,
        "scan_interval": 30,
    }


@pytest.fixture
def sample_container_data():
    """Sample container data for testing."""
    return {
        "Id": "test_container_id",
        "Names": ["/test-container"],
        "State": "running",
        "Status": "Up 2 hours",
        "Image": "nginx:latest",
        "Ports": [
            {
                "IP": "0.0.0.0",
                "PrivatePort": 80,
                "PublicPort": 8080,
                "Type": "tcp",
            }
        ],
        "Labels": {
            "traefik.enable": "true",
            "traefik.http.routers.test.rule": "Host(`test.localhost`)",
        },
    }


@pytest.fixture
def sample_endpoint_data():
    """Sample endpoint data for testing."""
    return {
        "Id": 1,
        "Name": "local",
        "Type": 1,
        "URL": "unix:///var/run/docker.sock",
        "Status": 1,
    }
