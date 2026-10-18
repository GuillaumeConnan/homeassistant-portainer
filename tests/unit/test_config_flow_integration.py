"""Tests for Portainer config-flow selection and options handling."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.portainer.config_flow import (
    PortainerConfigFlow,
    PortainerOptionsFlow,
)
from custom_components.portainer.const import CONF_FEATURE_USE_ACTION_BUTTONS


@pytest.fixture
def mock_hass():
    """Create a Home Assistant mock that runs executor jobs inline."""
    hass = Mock()

    async def run_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=run_executor_job)
    return hass


@pytest.mark.asyncio
async def test_config_flow_builds_container_choices_from_selected_endpoints(mock_hass):
    """The selection form exposes container labels from the API."""
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    flow.options = {"name": "Test Portainer", "endpoints": ["1"]}
    flow.api = Mock()
    flow.api.get_endpoints.return_value = [
        {"id": 1, "name": "local", "status": 1},
        {"id": 2, "name": "remote", "status": 1},
    ]
    flow.api.get_containers.return_value = [
        {
            "id": "container-1",
            "name": "test-container",
            "status": "running",
            "endpoint_id": 1,
        }
    ]
    flow.api.get_stacks.return_value = [
        {"id": 3, "name": "test-stack", "endpoint_id": 1}
    ]

    with patch.object(
        flow, "async_show_form", return_value={"type": "form"}
    ) as show_form:
        result = await flow.async_step_select_items()

    assert result == {"type": "form"}
    flow.api.get_containers.assert_called_once_with(1)
    flow.api.get_stacks.assert_called_once_with(1)
    assert show_form.call_args.kwargs["description_placeholders"] == {
        "containers": "test-container [running]",
        "stacks": "test-stack",
    }


@pytest.mark.asyncio
async def test_config_flow_persists_container_and_stack_selections(mock_hass):
    """Submitted choices are stored in the config entry data."""
    flow = PortainerConfigFlow()
    flow.options = {"name": "Test Portainer", "endpoints": ["1"]}
    selected = {
        "containers": ["Test Portainer_1_test-container"],
        "stacks": ["3"],
        CONF_FEATURE_USE_ACTION_BUTTONS: False,
    }

    with patch.object(
        flow, "async_create_entry", return_value={"type": "create_entry"}
    ) as create_entry:
        result = await flow.async_step_select_items(selected)

    assert result == {"type": "create_entry"}
    assert flow.options["containers"] == selected["containers"]
    assert flow.options["stacks"] == selected["stacks"]
    assert flow.options[CONF_FEATURE_USE_ACTION_BUTTONS] is False
    create_entry.assert_called_once_with(title="Test Portainer", data=flow.options)


@pytest.mark.asyncio
async def test_options_flow_reads_endpoint_selections(mock_hass):
    """The options flow displays the selected endpoint choices."""
    config_entry = Mock()
    config_entry.data = {
        "name": "Test Portainer",
        "host": "localhost:9000",
        "api_key": "test-key",
        "ssl": False,
        "verify_ssl": True,
    }
    config_entry.options = {"endpoints": ["1"]}
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    api = Mock()
    api.get_endpoints.return_value = [{"id": 1, "name": "local", "status": 1}]

    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ):
        flow.config_entry = config_entry
        with patch.object(
            flow, "async_show_form", return_value={"type": "form"}
        ) as show_form:
            result = await flow.async_step_init()

    assert result == {"type": "form"}
    assert show_form.call_args.kwargs["step_id"] == "init"
