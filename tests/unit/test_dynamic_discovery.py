"""Regression tests for resources which appear after platform setup."""

import asyncio
from importlib import import_module
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.portainer.const import DOMAIN


@pytest.mark.asyncio
@pytest.mark.parametrize("platform_name", ["sensor", "button"])
async def test_coordinator_updates_discover_resources_once_and_unsubscribe(
    platform_name,
):
    """Discovery uses coordinator callbacks, not a never-emitted dispatcher signal."""
    platform = import_module(f"custom_components.portainer.{platform_name}")
    hass = Mock()
    entry = Mock(entry_id="entry")
    coordinator = Mock(
        create_action_buttons=True, features={}, last_update_success=True
    )
    hass.data = {DOMAIN: {"entry": {"coordinator": coordinator}}}
    tasks = []

    def create_task(coroutine):
        task = asyncio.create_task(coroutine)
        tasks.append(task)
        return task

    hass.async_create_task.side_effect = create_task
    available_entities = []

    async def create_entities(*args):
        return list(available_entities)

    add_entities = Mock()
    with patch.object(
        platform, "async_create_sensors", side_effect=create_entities
    ), patch(
        "custom_components.portainer.sensor.async_migrate_entities",
        new_callable=AsyncMock,
    ), patch(
        "custom_components.portainer.sensor.ep.async_get_current_platform"
    ) as current_platform:
        current_platform.return_value.platform.SENSOR_SERVICES = []
        await platform.async_setup_entry(hass, entry, add_entities)
        listener = coordinator.async_add_listener.call_args.args[0]
        entry.async_on_unload.assert_called_once_with(
            coordinator.async_add_listener.return_value
        )
        add_entities.reset_mock()

        coordinator.last_update_success = False
        listener()
        assert not tasks
        coordinator.last_update_success = True
        available_entities.extend(
            [
                Mock(unique_id="container-sensor-or-button"),
                Mock(unique_id="stack-sensor-or-button"),
            ]
        )
        listener()
        listener()
        await asyncio.gather(*tasks)

    add_entities.assert_called_once_with(available_entities, update_before_add=True)


@pytest.mark.asyncio
async def test_disabled_action_buttons_do_not_register_discovery():
    """The action-button option applies to dynamic entities too."""
    from custom_components.portainer.button import async_setup_entry

    coordinator = Mock(create_action_buttons=False)
    hass = Mock(data={DOMAIN: {"entry": {"coordinator": coordinator}}})
    add_entities = Mock()
    await async_setup_entry(hass, Mock(entry_id="entry"), add_entities)
    coordinator.async_add_listener.assert_not_called()
    add_entities.assert_not_called()
