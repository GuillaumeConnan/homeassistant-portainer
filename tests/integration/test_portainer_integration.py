"""Tests for Home Assistant config-entry lifecycle handling."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.portainer import (
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.portainer.const import DOMAIN, PLATFORMS


@pytest.mark.asyncio
async def test_setup_entry_stores_coordinator_and_forwards_platforms():
    """Set up a config entry and forward setup to all integration platforms."""
    hass = Mock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    config_entry = Mock()
    config_entry.entry_id = "test-entry"
    config_entry.async_on_unload = Mock()
    config_entry.add_update_listener = Mock()
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.portainer.PortainerCoordinator", return_value=coordinator
        ),
        patch(
            "custom_components.portainer.async_register_services",
            new_callable=AsyncMock,
        ) as register_services,
        patch("custom_components.portainer._REGISTERED_DOMAINS", set()),
    ):
        assert await async_setup_entry(hass, config_entry) is True

    assert hass.data[DOMAIN]["test-entry"]["coordinator"] is coordinator
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    register_services.assert_awaited_once_with(hass)
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        config_entry, PLATFORMS
    )
    config_entry.async_on_unload.assert_called_once()
    config_entry.add_update_listener.assert_called_once_with(_async_update_listener)


@pytest.mark.asyncio
async def test_update_listener_reloads_entry():
    """The registered listener handles reloads for connection and options changes."""
    hass = Mock()
    hass.config_entries.async_reload = AsyncMock()
    entry = Mock(entry_id="entry")

    await _async_update_listener(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("entry")


@pytest.mark.asyncio
async def test_unload_entry_removes_coordinator_and_unregisters_services():
    """Unload the last config entry and remove its registered services."""
    hass = Mock()
    coordinator = Mock()
    coordinator.async_shutdown = AsyncMock()
    hass.data = {DOMAIN: {"test-entry": {"coordinator": coordinator}}}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    config_entry = Mock()
    config_entry.entry_id = "test-entry"
    registered_domains = {DOMAIN}

    with (
        patch("custom_components.portainer._REGISTERED_DOMAINS", registered_domains),
        patch(
            "custom_components.portainer.async_unregister_services",
            new_callable=AsyncMock,
        ) as unregister_services,
    ):
        assert await async_unload_entry(hass, config_entry) is True

    assert hass.data[DOMAIN] == {}
    coordinator.async_shutdown.assert_awaited_once()
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        config_entry, PLATFORMS
    )
    unregister_services.assert_awaited_once_with(hass)
    assert DOMAIN not in registered_domains


@pytest.mark.asyncio
@pytest.mark.parametrize("unload_ok", [True, False])
async def test_unload_preserves_other_entries_and_failed_unloads(unload_ok):
    """Only stop the unloaded coordinator, and retain it on platform failure."""
    coordinator = Mock(async_shutdown=AsyncMock())
    other_coordinator = Mock(async_shutdown=AsyncMock())
    hass = Mock()
    hass.data = {
        DOMAIN: {
            "entry": {"coordinator": coordinator},
            "other": {"coordinator": other_coordinator},
        }
    }
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=unload_ok)

    with patch(
        "custom_components.portainer.async_unregister_services",
        new_callable=AsyncMock,
    ) as unregister_services:
        assert await async_unload_entry(hass, Mock(entry_id="entry")) is unload_ok

    assert ("entry" in hass.data[DOMAIN]) is not unload_ok
    assert coordinator.async_shutdown.await_count == int(unload_ok)
    other_coordinator.async_shutdown.assert_not_awaited()
    unregister_services.assert_not_awaited()
