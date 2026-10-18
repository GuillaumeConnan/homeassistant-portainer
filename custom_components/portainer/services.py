"""Services for the Portainer integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .api import PortainerAPI

if TYPE_CHECKING:
    from .coordinator import PortainerCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_PERFORM_CONTAINER_ACTION = "perform_container_action"
SERVICE_PERFORM_STACK_ACTION = "perform_stack_action"
SERVICE_RECREATE_CONTAINER = "recreate_container"
ATTR_ACTION = "action"
ATTR_CONTAINER_DEVICES = "container_devices"
ATTR_STACK_DEVICES = "stack_devices"


async def async_execute_action(
    hass: HomeAssistant,
    api: PortainerAPI,
    service_path: str,
    method: str,
    params: dict[str, Any],
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Report API failures consistently, including successful empty responses."""
    try:
        result = await hass.async_add_executor_job(
            api.query, service_path, method, params
        )
    except Exception as error:
        raise HomeAssistantError(f"Portainer action failed: {error}") from error
    if api.error:
        raise HomeAssistantError(f"Portainer action failed: {api.error}")
    return result


def _resolve_device(
    hass: HomeAssistant, registry: dr.DeviceRegistry, device_id: str, model: str
) -> tuple[PortainerCoordinator, str]:
    """Resolve an exact integration identifier to a loaded coordinator."""
    device = registry.async_get(device_id)
    if not device:
        raise HomeAssistantError(f"Device '{device_id}' not found")
    if device.model != model:
        raise HomeAssistantError(f"Device '{device_id}' is not a Portainer {model}")
    for entry_id in device.config_entries:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
        coordinator = entry_data.get("coordinator")
        if coordinator is None:
            continue
        prefix = f"{entry_id}_stack_" if model == "Stack" else f"{entry_id}_"
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith(prefix):
                resource = identifier[len(prefix) :]
                if model == "Stack" and resource.isdigit():
                    return coordinator, resource
                if model == "Container":
                    endpoint_id, separator, name = resource.partition("_")
                    if endpoint_id.isdigit() and separator and name:
                        return coordinator, resource
    raise HomeAssistantError(
        f"Device '{device_id}' has no valid identifier for a loaded Portainer entry"
    )


async def _async_handle_action(
    call: ServiceCall, *, model: str, recreate: bool = False
) -> None:
    """Attempt all targets, refresh changed entries and report every failure."""
    hass = call.hass
    action = "recreate" if recreate else call.data.get(ATTR_ACTION)
    if recreate:
        allowed = ("recreate",)
    elif model == "Stack":
        allowed = ("start", "stop")
    else:
        allowed = ("start", "stop", "restart", "kill", "remove")
    if action not in allowed:
        raise HomeAssistantError(f"Unsupported Portainer action: {action}")
    targets = call.data.get(
        ATTR_STACK_DEVICES if model == "Stack" else ATTR_CONTAINER_DEVICES
    )
    if not targets:
        raise HomeAssistantError("No Portainer devices provided")

    registry = dr.async_get(hass)
    errors: list[str] = []
    coordinators: set[PortainerCoordinator] = set()
    for device_id in targets:
        try:
            coordinator, resource = _resolve_device(hass, registry, device_id, model)
            coordinators.add(coordinator)
            if model == "Stack":
                stack = await async_execute_action(
                    hass, coordinator.api, f"stacks/{resource}", "GET", {}
                )
                if not isinstance(stack, dict) or not stack.get("EndpointId"):
                    raise HomeAssistantError(
                        f"Stack '{resource}' or its endpoint not found"
                    )
                await async_execute_action(
                    hass,
                    coordinator.api,
                    f"stacks/{resource}/{action}?endpointId={stack['EndpointId']}",
                    "POST",
                    {},
                )
            else:
                endpoint_id, name = resource.split("_", 1)
                if recreate:
                    if not await coordinator.async_recreate_container(
                        endpoint_id, name, call.data.get("pull_image", True)
                    ):
                        raise HomeAssistantError(
                            f"Failed to recreate '{name}': {coordinator.api.error or 'container not found'}"
                        )
                else:
                    container = coordinator.get_specific_container(endpoint_id, name)
                    if not container or not container.get("Id"):
                        raise HomeAssistantError(
                            f"Container '{name}' not found on endpoint {endpoint_id}"
                        )
                    path = (
                        f"endpoints/{endpoint_id}/docker/containers/{container['Id']}"
                    )
                    params = {}
                    method = "POST"
                    if action == "remove":
                        method = "DELETE"
                        params = {
                            "force": str(call.data.get("force", False)).lower(),
                            "v": str(call.data.get("remove_volumes", False)).lower(),
                        }
                    else:
                        path += f"/{action}"
                    await async_execute_action(
                        hass, coordinator.api, path, method, params
                    )
                    if action == "remove":
                        entity_registry = er.async_get(hass)
                        for entity in er.async_entries_for_device(
                            entity_registry, device_id, include_disabled_entities=True
                        ):
                            entity_registry.async_remove(entity.entity_id)
                        registry.async_remove_device(device_id)
            _LOGGER.info(
                "Successfully performed '%s' on Portainer device '%s'",
                action,
                device_id,
            )
        except Exception as error:
            _LOGGER.error(
                "Failed to perform '%s' on device '%s': %s", action, device_id, error
            )
            errors.append(f"{device_id}: {error}")

    for coordinator in coordinators:
        try:
            await coordinator.async_request_refresh()
        except Exception as error:
            errors.append(f"Refresh failed: {error}")
    if errors:
        raise HomeAssistantError(
            f"Failed to {action} Portainer {'containers' if model == 'Container' else 'stacks'}: "
            + "; ".join(errors)
        )


async def _handle_recreate_container(call: ServiceCall) -> None:
    """Handle container recreation."""
    await _async_handle_action(call, model="Container", recreate=True)


async def _handle_perform_container_action(call: ServiceCall) -> None:
    """Handle container actions."""
    await _async_handle_action(call, model="Container")


async def _handle_perform_stack_action(call: ServiceCall) -> None:
    """Handle stack actions."""
    await _async_handle_action(call, model="Stack")


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the Portainer services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_PERFORM_CONTAINER_ACTION,
        _handle_perform_container_action,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ACTION): vol.In(
                    ["start", "stop", "restart", "kill", "remove"]
                ),
                vol.Required(ATTR_CONTAINER_DEVICES): vol.All([str], vol.Length(min=1)),
                vol.Optional("force", default=False): bool,
                vol.Optional("remove_volumes", default=False): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PERFORM_STACK_ACTION,
        _handle_perform_stack_action,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ACTION): vol.In(["start", "stop"]),
                vol.Required(ATTR_STACK_DEVICES): vol.All([str], vol.Length(min=1)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECREATE_CONTAINER,
        _handle_recreate_container,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONTAINER_DEVICES): vol.All([str], vol.Length(min=1)),
                vol.Optional("pull_image", default=True): bool,
            }
        ),
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister the Portainer services."""
    hass.services.async_remove(DOMAIN, SERVICE_PERFORM_CONTAINER_ACTION)
    hass.services.async_remove(DOMAIN, SERVICE_PERFORM_STACK_ACTION)
    hass.services.async_remove(DOMAIN, SERVICE_RECREATE_CONTAINER)
