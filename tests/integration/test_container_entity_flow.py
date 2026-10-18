"""Integration tests for Portainer container data processing."""

from unittest.mock import Mock, patch

import pytest

from custom_components.portainer.coordinator import PortainerCoordinator


@pytest.mark.parametrize(
    ("container_name", "selected"),
    [("web-server", True), ("database", False)],
)
@pytest.mark.parametrize(
    "selection",
    ["test-entry_1_web-server", "Test Portainer_1_web-server", "1_web-server"],
)
def test_container_selection_filters_portainer_api_results(
    container_name, selected, selection
):
    """Only containers selected in the config entry are exposed by the coordinator."""
    hass = Mock()
    config_entry = Mock()
    config_entry.entry_id = "test-entry"
    config_entry.data = {
        "name": "Test Portainer",
        "host": "localhost:9000",
        "api_key": "test-key",
        "ssl": False,
        "verify_ssl": True,
        "endpoints": ["1"],
    }
    config_entry.options = {
        "endpoints": ["1"],
        "containers": [selection],
        "stacks": [],
    }
    api = Mock()
    api.query.side_effect = lambda url, *args, **kwargs: (
        [
            {
                "Id": "container-1",
                "Names": ["/web-server"],
                "State": "running",
            },
            {
                "Id": "container-2",
                "Names": ["/database"],
                "State": "running",
            },
        ]
        if "containers/json" in url
        else {
            "Id": url.split("/")[-2],
            "State": {"Status": "running"},
            "HostConfig": {"NetworkMode": "bridge"},
            "NetworkSettings": {"Networks": {}},
            "Mounts": [],
        }
    )

    with patch(
        "custom_components.portainer.coordinator.PortainerAPI", return_value=api
    ), patch("homeassistant.helpers.frame.report_usage"):
        coordinator = PortainerCoordinator(hass, config_entry)

    coordinator.raw_data = {
        "endpoints": {1: {"Status": 1, "Name": "local"}},
        "containers": {},
        "stacks": {},
    }
    coordinator.get_containers()

    key = f"test-entry_1_{container_name}"
    assert (key in coordinator.raw_data["containers"]) is selected
