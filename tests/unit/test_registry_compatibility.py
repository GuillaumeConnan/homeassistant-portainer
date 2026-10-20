"""Regression tests for device lookups before platform attachment."""

from unittest.mock import Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.portainer.button import BUTTON_TYPES, ContainerActionButton
from custom_components.portainer.repairs import async_create_fix_flow
from custom_components.portainer.sensor import ContainerSensor, async_migrate_entities
from custom_components.portainer.sensor_types import SENSOR_TYPES
from custom_components.portainer.services import _resolve_device


@pytest.mark.parametrize(
    ("model", "identifier", "resource"),
    [
        ("Container", "entry_1_web_api", "1_web_api"),
        ("Stack", "entry_stack_2", "2"),
    ],
)
@pytest.mark.parametrize("loaded", [True, False])
def test_service_targets_use_single_config_entry(model, identifier, resource, loaded):
    """Service resolution never reads the deprecated config_entries property."""
    coordinator = Mock()
    hass = Mock(data={"portainer": {"entry": {"coordinator": coordinator}}})
    if not loaded:
        hass.data["portainer"].clear()
    device = Mock(
        spec=["model", "identifiers", "config_entry_id"],
        model=model,
        identifiers={("portainer", identifier)},
        config_entry_id="entry",
    )
    registry = Mock()
    registry.async_get.return_value = device

    if loaded:
        assert _resolve_device(hass, registry, "device", model) == (
            coordinator,
            resource,
        )
    else:
        with pytest.raises(HomeAssistantError, match="no valid identifier"):
            _resolve_device(hass, registry, "device", model)


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["sensor", "button"])
@pytest.mark.parametrize("device_exists", [True, False])
async def test_migrate_unattached_container_entities(platform, device_exists):
    """Migration resolves parents and containers before entity.hass is assigned."""
    hass = Mock()
    coordinator = Mock(hass=hass)
    coordinator.config_entry.entry_id = "entry"
    coordinator.config_entry.data = {"name": "Portainer"}
    coordinator.api._url = "http://localhost:9000/api/"
    coordinator.data = {
        "endpoints": {"1": {"DockerVersion": "24.0.6"}},
        "containers": {
            "entry_1_web": {
                "Id": "container-id",
                "Name": "web",
                "EndpointId": 1,
                "State": "running",
            }
        },
    }
    if platform == "sensor":
        entity = ContainerSensor(coordinator, SENSOR_TYPES[1], "entry_1_web")
    else:
        entity = ContainerActionButton(coordinator, BUTTON_TYPES[0], "entry_1_web")
    assert entity.hass is None

    devices = Mock()
    devices.async_get_device_by_identifier.side_effect = [
        Mock(id="endpoint-device"),
        Mock(id="container-device") if device_exists else None,
    ]
    existing = Mock(
        entity_id=f"{platform}.web",
        unique_id=f"portainer-{entity.description.key}-old-id",
        platform="portainer",
        disabled_by=None,
    )

    def get_registry(instance):
        assert instance is hass
        return devices

    with patch(
        "custom_components.portainer.entity.dr.async_get", side_effect=get_registry
    ), patch(
        "custom_components.portainer.sensor.er.async_get"
    ) as entity_registry, patch(
        "custom_components.portainer.sensor.er.async_entries_for_device",
        return_value=[existing],
    ):
        await async_migrate_entities(hass, coordinator.config_entry, [entity])

    assert [
        call.args for call in devices.async_get_device_by_identifier.call_args_list
    ] == [
        (("portainer", "1_entry"), "entry"),
        (("portainer", "entry_1_web"), "entry"),
    ]
    devices.async_get_device.assert_not_called()
    update = entity_registry.return_value.async_update_entity
    if device_exists:
        update.assert_called_once_with(
            existing.entity_id, new_unique_id=entity.unique_id
        )
    else:
        update.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["container", "endpoint", "stack"])
async def test_repairs_use_saved_device_id(kind):
    """Repair confirmation and deletion target the same saved registry device."""
    hass = Mock()
    device = Mock(id="target-device", name_by_user=None)
    device.name = "My resource"
    with patch(
        "custom_components.portainer.repairs.dr.async_get"
    ) as get_registry, patch(
        "custom_components.portainer.repairs.er.async_get"
    ) as get_entities, patch(
        "custom_components.portainer.repairs.er.async_entries_for_device",
        return_value=[Mock(entity_id="sensor.resource")],
    ):
        registry = get_registry.return_value
        registry.async_get.return_value = device
        flow = await async_create_fix_flow(
            hass, f"missing_{kind}_entry_resource", {"device_id": "target-device"}
        )
        form = await flow.async_step_init()
        assert form["step_id"] == "confirm"
        assert form["description_placeholders"] == {"device_name": "My resource"}
        registry.async_remove_device.assert_not_called()

        result = await flow.async_step_confirm({})

    assert result["type"] == "create_entry"
    assert [call.args for call in registry.async_get.call_args_list] == [
        ("target-device",),
        ("target-device",),
    ]
    registry.async_get_device.assert_not_called()
    registry.async_remove_device.assert_called_once_with("target-device")
    get_entities.return_value.async_remove.assert_called_once_with("sensor.resource")


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [None, {"device_id": "already-removed"}])
async def test_repair_without_existing_target_does_not_remove_other_devices(data):
    """A missing repair target is not replaced by an ambiguous identifier lookup."""
    with patch("custom_components.portainer.repairs.dr.async_get") as get_registry:
        registry = get_registry.return_value
        registry.async_get.return_value = None
        flow = await async_create_fix_flow(Mock(), "missing_stack_entry_1", data)
        result = await flow.async_step_confirm({})

    assert result["type"] == "create_entry"
    registry.async_get_device.assert_not_called()
    registry.async_remove_device.assert_not_called()
