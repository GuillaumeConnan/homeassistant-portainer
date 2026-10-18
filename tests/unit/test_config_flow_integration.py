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
    flow.api.get_stacks.assert_called_once_with()
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


@pytest.mark.asyncio
@pytest.mark.parametrize("options_flow", [False, True])
async def test_stack_inventory_is_fetched_once_for_selected_active_endpoints(
    mock_hass, options_flow
):
    """Setup and options both filter a single stack response locally."""
    entry = Mock()
    entry.entry_id = "entry"
    entry.data = {
        "name": "Portainer",
        "host": "localhost:9443",
        "api_key": "test-key",
        "ssl": True,
        "verify_ssl": False,
    }
    entry.options = {"endpoints": ["1", "2", "3"], "stacks": ["11", "22"]}
    api = Mock()
    api.get_endpoints.return_value = [
        {"id": 1, "status": 1},
        {"id": "2", "status": 1},
        {"id": 3, "status": 2},
        {"id": 4, "status": 1},
    ]
    api.get_containers.return_value = []
    api.get_stacks.return_value = [
        {"id": "11", "name": "local-stack", "endpoint_id": "1"},
        {"id": "22", "name": "remote-stack", "endpoint_id": 2},
        {"id": "33", "name": "offline-stack", "endpoint_id": "3"},
        {"id": "44", "name": "unselected-stack", "endpoint_id": "4"},
    ]
    flow = PortainerOptionsFlow() if options_flow else PortainerConfigFlow()
    flow.hass = mock_hass
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(flow, "async_show_form", return_value={}) as show_form:
        if options_flow:
            flow.config_entry = entry
        else:
            flow.api = api
            flow.options = {**entry.data, **entry.options}
        await flow.async_step_select_items()

    api.get_stacks.assert_called_once_with()
    assert api.get_containers.call_count == 2
    assert show_form.call_args.kwargs["description_placeholders"]["stacks"] == (
        "local-stack, remote-stack"
    )
    if options_flow:
        schema = show_form.call_args.kwargs["data_schema"]
        assert schema({})["stacks"] == ["11", "22"]


@pytest.mark.asyncio
@pytest.mark.parametrize("options_flow", [False, True])
async def test_failed_stack_fetch_aborts_selection(mock_hass, options_flow):
    """Do not save an empty stack selection on an API outage."""
    api = Mock()
    api.get_endpoints.return_value = [{"id": 1, "status": 1}]
    api.get_containers.return_value = []
    api.get_stacks.side_effect = ValueError("Unable to fetch stacks")
    flow = PortainerOptionsFlow() if options_flow else PortainerConfigFlow()
    flow.hass = mock_hass
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(flow, "async_abort", return_value={}) as abort:
        if options_flow:
            flow.config_entry = Mock(
                data={
                    "host": "host",
                    "api_key": "test",
                    "ssl": True,
                    "verify_ssl": True,
                },
                options={"endpoints": ["1"], "stacks": ["11"]},
            )
        else:
            flow.api = api
            flow.options = {"name": "Portainer", "endpoints": ["1"]}
        await flow.async_step_select_items()

    abort.assert_called_once_with(reason="item_fetch_failed")


@pytest.mark.parametrize("verify_ssl", [True, False])
def test_config_form_preserves_explicit_tls_choice(verify_ssl):
    """Retrying a failed connection must not reset the user's TLS choices."""
    flow = PortainerConfigFlow()
    user_input = {
        "name": "Test",
        "host": "localhost",
        "api_key": "test",
        "ssl": False,
        "verify_ssl": verify_ssl,
    }
    with patch.object(flow, "async_show_form", return_value={}) as show_form:
        flow._show_config_form(user_input, errors={"host": "no_response"})

    defaults = show_form.call_args.kwargs["data_schema"](
        {"name": "Test", "host": "localhost", "api_key": "test"}
    )
    assert defaults["ssl"] is False
    assert defaults["verify_ssl"] is verify_ssl


def test_config_form_defaults_to_verified_https():
    """New entries verify TLS certificates by default."""
    flow = PortainerConfigFlow()
    with patch.object(flow, "async_show_form", return_value={}) as show_form:
        flow._show_config_form(None)

    defaults = show_form.call_args.kwargs["data_schema"](
        {"name": "Test", "host": "localhost", "api_key": "test"}
    )
    assert defaults["ssl"] is True
    assert defaults["verify_ssl"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_persists_tls_choice_through_endpoint_and_stack_selection(
    mock_hass, verify_ssl
):
    """Both trusted HTTPS and an explicit self-signed opt-out survive setup."""
    mock_hass.config_entries.async_entries.return_value = []
    credentials = {
        "name": "Portainer",
        "host": "localhost:9443",
        "api_key": "test-key",
        "ssl": True,
        "verify_ssl": verify_ssl,
    }
    api = Mock()
    api.connection_test.return_value = (True, "")
    api.get_endpoints.return_value = [{"id": "1", "name": "local", "status": 1}]
    api.get_containers.return_value = []
    api.get_stacks.return_value = [
        {"id": "11", "name": "web-stack", "endpoint_id": "1"}
    ]
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    with patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ) as api_class, patch.object(
        flow, "async_show_form", return_value={}
    ) as show_form, patch.object(
        flow, "async_create_entry", return_value={}
    ) as create_entry:
        await flow.async_step_user(credentials.copy())
        assert show_form.call_args.kwargs["step_id"] == "endpoints"
        api_class.assert_called_once_with(
            mock_hass, "localhost:9443", "test-key", True, verify_ssl
        )
        await flow.async_step_endpoints({"endpoints": ["1"]})
        assert show_form.call_args.kwargs["step_id"] == "select_items"
        api.get_stacks.assert_called_once_with()
        await flow.async_step_select_items({"containers": [], "stacks": ["11"]})

    saved = create_entry.call_args.kwargs["data"]
    assert saved["verify_ssl"] is verify_ssl
    assert saved["ssl"] is True
    assert saved["stacks"] == ["11"]
    assert saved["endpoints"] == ["1"]


@pytest.mark.asyncio
async def test_failed_connection_preserves_unverified_tls_on_retry(mock_hass):
    """A network failure must not silently re-enable verification on the retry form."""
    mock_hass.config_entries.async_entries.return_value = []
    api = Mock()
    api.connection_test.return_value = (False, "no_response")
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    with patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(flow, "async_show_form", return_value={}) as show_form:
        await flow.async_step_user(
            {
                "name": "Portainer",
                "host": "localhost:9443",
                "api_key": "test",
                "ssl": True,
                "verify_ssl": False,
            }
        )

    assert show_form.call_args.kwargs["errors"] == {"host": "no_response"}
    defaults = show_form.call_args.kwargs["data_schema"](
        {"name": "Portainer", "host": "localhost:9443", "api_key": "test"}
    )
    assert defaults["verify_ssl"] is False
    api.get_endpoints.assert_not_called()


@pytest.mark.asyncio
async def test_no_active_endpoints_skips_stack_fetch(mock_hass):
    """There is no stack request when no selected endpoint is reachable."""
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    flow.options = {"name": "Portainer", "endpoints": ["1"]}
    flow.api = Mock()
    flow.api.get_endpoints.return_value = [{"id": 1, "name": "local", "status": 2}]
    with patch.object(flow, "async_show_form", return_value={}) as show_form:
        await flow.async_step_select_items()

    flow.api.get_stacks.assert_not_called()
    flow.api.get_containers.assert_not_called()
    assert show_form.call_args.kwargs["description_placeholders"]["stacks"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("available_endpoints", [[], [{"id": "1", "name": "local"}]])
async def test_endpoint_selection_requires_an_endpoint(mock_hass, available_endpoints):
    """Setup never fetches stacks before valid endpoint selection."""
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    flow.options = {"name": "Portainer"}
    flow.api = Mock()
    flow.api.get_endpoints.return_value = available_endpoints
    with patch.object(flow, "async_show_form", return_value={}) as show_form:
        await flow.async_step_endpoints({"endpoints": []})

    errors = show_form.call_args.kwargs["errors"]
    assert errors["base"] == (
        "no_endpoints_selected" if available_endpoints else "no_endpoints_found"
    )
    flow.api.get_stacks.assert_not_called()


@pytest.mark.asyncio
async def test_options_save_keeps_stack_selections_and_existing_tls_setting(mock_hass):
    """Saving a batched stack selection preserves unchanged devices and saved TLS."""
    entry = Mock()
    entry.entry_id = "entry"
    entry.data = {"verify_ssl": False}
    entry.options = {
        "endpoints": ["1", "2"],
        "containers": ["entry_1_web"],
        "stacks": ["11", "22"],
    }
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    flow.options = entry.options.copy()
    selection = {
        "containers": ["entry_1_web"],
        "stacks": ["11", "22"],
        CONF_FEATURE_USE_ACTION_BUTTONS: True,
    }
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.dr"
    ) as mock_dr, patch("custom_components.portainer.config_flow.er"), patch.object(
        flow, "async_create_entry", return_value={}
    ) as create_entry:
        flow.config_entry = entry
        mock_dr.async_entries_for_config_entry.return_value = []
        await flow.async_step_select_items(selection)

    mock_dr.async_get.return_value.async_remove_device.assert_not_called()
    saved = create_entry.call_args.kwargs["data"]
    assert saved["stacks"] == ["11", "22"]
    assert saved["containers"] == ["entry_1_web"]
    assert saved["endpoints"] == ["1", "2"]
    assert entry.data["verify_ssl"] is False
