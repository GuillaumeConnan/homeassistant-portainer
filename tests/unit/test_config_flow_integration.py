"""Tests for Portainer config-flow selection and options handling."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.portainer.config_flow import (
    PortainerConfigFlow,
    PortainerOptionsFlow,
)
from custom_components.portainer.const import CONF_FEATURE_USE_ACTION_BUTTONS


def set_options_entry(flow, entry):
    """Link the options flow through Home Assistant's config-entry lookup."""
    flow.handler = entry.entry_id
    flow.hass.config_entries.async_get_known_entry.return_value = entry


@pytest.fixture
def mock_hass():
    """Create a Home Assistant mock that runs executor jobs inline."""
    hass = Mock()
    hass.data = {}

    async def run_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=run_executor_job)
    with patch("custom_components.portainer.config_flow.dr.async_get"), patch(
        "custom_components.portainer.config_flow.dr.async_entries_for_config_entry",
        return_value=[],
    ):
        yield hass


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
        set_options_entry(flow, config_entry)
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
            set_options_entry(flow, entry)
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
            entry = Mock(
                data={
                    "host": "host",
                    "api_key": "test",
                    "ssl": True,
                    "verify_ssl": True,
                },
                options={"endpoints": ["1"], "stacks": ["11"]},
            )
            set_options_entry(flow, entry)
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

    assert show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}
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
        set_options_entry(flow, entry)
        mock_dr.async_entries_for_config_entry.return_value = []
        await flow.async_step_select_items(selection)

    mock_dr.async_get.return_value.async_remove_device.assert_not_called()
    saved = create_entry.call_args.kwargs["data"]
    assert saved["stacks"] == ["11", "22"]
    assert saved["containers"] == ["1_web"]
    assert saved["endpoints"] == ["1", "2"]
    assert entry.data["verify_ssl"] is False


@pytest.fixture
def selection_entry():
    """Entry with historical selections stored before the first options save."""
    return Mock(
        entry_id="entry",
        data={
            "name": "My_Portainer",
            "host": "host:9443",
            "api_key": "token",
            "ssl": True,
            "verify_ssl": True,
            "endpoints": ["1", "10"],
            "containers": ["My_Portainer_1_web_api", "entry_10_database"],
            "stacks": ["1", "10"],
            CONF_FEATURE_USE_ACTION_BUTTONS: False,
        },
        options={},
    )


@pytest.mark.asyncio
async def test_setup_uses_endpoint_name_selection_identifiers(mock_hass):
    """New selection IDs do not depend on an entry ID or integration name."""
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    flow.options = {"name": "My_Portainer", "endpoints": ["1"]}
    flow.api = Mock()
    flow.api.get_endpoints.return_value = [{"id": "1", "status": 1}]
    flow.api.get_containers.return_value = [
        {"endpoint_id": "1", "name": "web_api", "status": "running"}
    ]
    flow.api.get_stacks.return_value = []
    with patch.object(flow, "async_show_form", return_value={}) as show:
        await flow.async_step_select_items()
    schema = show.call_args.kwargs["data_schema"]
    assert schema({"containers": ["1_web_api"]})["containers"] == ["1_web_api"]


@pytest.mark.asyncio
@pytest.mark.parametrize("offline", [True, False])
async def test_options_keep_missing_resources_and_normalize_legacy_defaults(
    mock_hass, selection_entry, offline
):
    """Absent resources remain checked, including before the first options save."""
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    api = Mock()
    api.get_endpoints.return_value = [{"id": "1", "status": 2 if offline else 1}]
    api.get_containers.return_value = []
    api.get_stacks.return_value = []
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(flow, "async_show_form", return_value={}) as show:
        set_options_entry(flow, selection_entry)
        await flow.async_step_select_items()
    defaults = show.call_args.kwargs["data_schema"]({})
    assert defaults["containers"] == ["1_web_api", "10_database"]
    assert defaults["stacks"] == ["1", "10"]
    assert defaults[CONF_FEATURE_USE_ACTION_BUTTONS] is False
    if offline:
        api.get_containers.assert_not_called()
        api.get_stacks.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_form_retains_unlisted_saved_endpoints(
    mock_hass, selection_entry
):
    """A temporarily absent endpoint remains an explicit selectable choice."""
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    api = Mock()
    api.get_endpoints.return_value = []
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(flow, "async_show_form", return_value={}) as show:
        set_options_entry(flow, selection_entry)
        await flow.async_step_init()
    assert show.call_args.kwargs["data_schema"]({})["endpoints"] == ["1", "10"]


@pytest.mark.asyncio
async def test_endpoint_changes_are_staged_until_final_submission(
    mock_hass, selection_entry
):
    """Abandoning the second screen cannot remove existing devices."""
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.dr"
    ) as registry, patch.object(
        flow, "async_step_select_items", new_callable=AsyncMock
    ):
        set_options_entry(flow, selection_entry)
        await flow.async_step_init({"endpoints": ["10"]})
    registry.async_get.assert_not_called()
    assert selection_entry.options == {}
    assert selection_entry.data["endpoints"] == ["1", "10"]


@pytest.mark.asyncio
@pytest.mark.parametrize("inventory_source", ["coordinator", "registry"])
async def test_offline_stacks_are_excluded_only_for_explicitly_removed_endpoints(
    mock_hass, selection_entry, inventory_source
):
    """Cached metadata distinguishes endpoint removal from an endpoint outage."""
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    flow.options = {"endpoints": ["10"]}
    api = Mock()
    api.get_endpoints.return_value = [{"id": "10", "status": 2}]
    devices = []
    if inventory_source == "coordinator":
        mock_hass.data = {
            "portainer": {
                "entry": {
                    "coordinator": Mock(
                        data={
                            "stacks": {"1": {"EndpointId": 1}, "10": {"EndpointId": 10}}
                        }
                    )
                }
            }
        }
    else:
        devices = [
            Mock(
                id="endpoint1", model="Endpoint", identifiers={("portainer", "1_entry")}
            ),
            Mock(
                id="endpoint10",
                model="Endpoint",
                identifiers={("portainer", "10_entry")},
            ),
            Mock(
                model="Stack",
                identifiers={("portainer", "entry_stack_1")},
                via_device_id="endpoint1",
            ),
            Mock(
                model="Stack",
                identifiers={("portainer", "entry_stack_10")},
                via_device_id="endpoint10",
            ),
        ]
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch(
        "custom_components.portainer.config_flow.dr.async_entries_for_config_entry",
        return_value=devices,
    ), patch.object(
        flow, "async_show_form", return_value={}
    ) as show:
        set_options_entry(flow, selection_entry)
        await flow.async_step_select_items()
    defaults = show.call_args.kwargs["data_schema"]({})
    assert defaults["containers"] == ["10_database"]
    assert defaults["stacks"] == ["10"]
    api.get_stacks.assert_not_called()


@pytest.mark.asyncio
async def test_failed_inventory_never_cleans_devices(mock_hass, selection_entry):
    """A failed second screen is non-destructive, including endpoint changes."""
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    flow.options = {"endpoints": ["10"]}
    api = Mock()
    api.get_endpoints.side_effect = ValueError("no_response")
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch("custom_components.portainer.config_flow.dr") as registry, patch.object(
        flow, "async_abort", return_value={}
    ):
        set_options_entry(flow, selection_entry)
        await flow.async_step_select_items()
    registry.async_get.assert_not_called()
    assert selection_entry.options == {}


@pytest.mark.asyncio
async def test_final_cleanup_matches_exact_typed_identifiers(
    mock_hass, selection_entry
):
    """Removing stack/endpoint 1 never removes stack/endpoint 10 or other types."""

    def device(identifier, model, device_id, parent=None, domain="portainer"):
        return Mock(
            identifiers={(domain, identifier)},
            model=model,
            id=device_id,
            via_device_id=parent,
            config_entries={"entry"},
        )

    devices = [
        device("1_entry", "Endpoint", "endpoint1"),
        device("10_entry", "Endpoint", "endpoint10"),
        device("entry_1_web_api", "Container", "container1", "endpoint1"),
        device("entry_10_database", "Container", "container10", "endpoint10"),
        device("entry_stack_1", "Stack", "stack1", "endpoint1"),
        device("entry_stack_10", "Stack", "stack10", "endpoint10"),
        device("entry_stack_1", "Container", "wrong_type"),
        device("entry_stack_1", "Stack", "foreign_domain", "endpoint1", domain="other"),
        device("entry_1_web_api_extra", "Container", "similar_name"),
    ]
    flow = PortainerOptionsFlow()
    flow.hass = mock_hass
    flow.options = {"endpoints": ["10"]}
    with patch("homeassistant.config_entries.report_usage"), patch(
        "custom_components.portainer.config_flow.dr"
    ) as registry, patch(
        "custom_components.portainer.config_flow.er"
    ) as entities, patch.object(
        flow, "async_create_entry", return_value={}
    ):
        set_options_entry(flow, selection_entry)
        registry.async_entries_for_config_entry.return_value = devices
        entities.async_entries_for_device.return_value = [
            Mock(entity_id="sensor.own", config_entry_id="entry"),
            Mock(entity_id="sensor.other", config_entry_id="other"),
        ]
        await flow.async_step_select_items(
            {"containers": ["10_database"], "stacks": ["10"]}
        )
    assert {
        call.args[0]
        for call in registry.async_get.return_value.async_remove_device.call_args_list
    } == {"endpoint1", "container1", "stack1"}
    assert all(
        call.args == ("sensor.own",)
        for call in entities.async_get.return_value.async_remove.call_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["reauth_confirm", "reconfigure"])
@pytest.mark.parametrize("error", [401, 403, "no_response", "invalid_json", ""])
async def test_connection_update_validates_before_saving_and_keeps_selections(
    mock_hass, selection_entry, step, error
):
    """Credentials are changed only after validation, without replacing selections."""
    flow = PortainerConfigFlow()
    flow.hass = mock_hass
    api = Mock()
    api.connection_test.return_value = (not error, error)
    credentials = {
        "host": "new-host:9443",
        "api_key": "new-token",
        "ssl": True,
        "verify_ssl": False,
    }
    with patch.object(
        flow, "_get_reauth_entry", return_value=selection_entry
    ), patch.object(
        flow, "_get_reconfigure_entry", return_value=selection_entry
    ), patch(
        "custom_components.portainer.config_flow.PortainerAPI", return_value=api
    ), patch.object(
        flow, "async_update_reload_and_abort", return_value={}
    ) as save, patch.object(
        flow, "async_show_form", return_value={}
    ) as show:
        await getattr(flow, f"async_step_{step}")(credentials)
    if error:
        save.assert_not_called()
        assert show.call_args.kwargs["errors"] == {
            "base": "invalid_auth" if error in (401, 403) else "cannot_connect"
        }
        defaults = show.call_args.kwargs["data_schema"]({})
        assert defaults == credentials
    else:
        save.assert_called_once_with(selection_entry, data_updates=credentials)
    assert selection_entry.data["containers"] == [
        "My_Portainer_1_web_api",
        "entry_10_database",
    ]
    assert selection_entry.options == {}
