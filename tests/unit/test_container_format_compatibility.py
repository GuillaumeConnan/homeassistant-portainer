"""Test compatibility with both supported container selection key formats."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from custom_components.portainer.coordinator import PortainerCoordinator
from custom_components.portainer.entity import async_create_sensors


@pytest.fixture
def coordinator():
    """Create a coordinator with containers selected by both identifier formats."""
    hass = Mock()
    config_entry = Mock()
    config_entry.entry_id = "entry-id"
    config_entry.data = {
        "name": "Test Portainer",
        "host": "localhost:9000",
        "api_key": "test-key",
        "ssl": False,
        "verify_ssl": True,
    }
    config_entry.options = {
        "containers": [
            "Test Portainer_2_ots-app-1",
            "entry-id_2_ots-redis-1",
        ]
    }

    with patch("custom_components.portainer.coordinator.PortainerAPI"), patch(
        "homeassistant.helpers.frame.report_usage"
    ):
        return PortainerCoordinator(hass, config_entry)


def test_coordinator_handles_both_container_selection_formats(coordinator):
    """The coordinator keeps selected containers in either supported key format."""
    api_response = [
        {"Id": "app", "Names": ["/ots-app-1"], "State": "running"},
        {"Id": "redis", "Names": ["/ots-redis-1"], "State": "running"},
    ]
    coordinator.api.query.side_effect = lambda url, *args, **kwargs: (
        api_response
        if "containers/json" in url
        else {
            "Id": url.split("/")[-2],
            "State": {"Status": "running"},
            "HostConfig": {"NetworkMode": "bridge"},
            "NetworkSettings": {"Networks": {}},
            "Mounts": [],
        }
    )
    coordinator.raw_data = {
        "endpoints": {2: {"Status": 1, "Name": "test-endpoint"}},
        "containers": {},
        "stacks": {},
    }

    coordinator.get_containers()

    assert set(coordinator.raw_data["containers"]) == {
        "entry-id_2_ots-app-1",
        "entry-id_2_ots-redis-1",
    }


@pytest.mark.asyncio
async def test_entity_creation_keeps_selected_containers(coordinator):
    """Selected container sensors are built for both identifier formats."""
    coordinator.data = {
        "containers": {
            "entry-id_2_ots-app-1": {
                "Name": "ots-app-1",
                "EndpointId": "2",
                "State": "running",
            },
            "entry-id_2_ots-redis-1": {
                "Name": "ots-redis-1",
                "EndpointId": "2",
                "State": "running",
            },
        }
    }
    description = SimpleNamespace(
        data_path="containers",
        data_attribute="State",
        data_name="Name",
        data_reference=True,
        func="ContainerSensor",
    )
    create_entity = Mock()

    entities = await async_create_sensors(
        coordinator, [description], {"ContainerSensor": create_entity}
    )

    assert len(entities) == 2
    assert create_entity.call_count == 2
