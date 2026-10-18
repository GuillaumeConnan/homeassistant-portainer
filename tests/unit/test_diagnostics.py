"""Tests for credential redaction in downloadable diagnostics."""

from unittest.mock import Mock

import pytest

from custom_components.portainer.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_credentials_without_mutating_config():
    """Credentials in data, options and nested coordinator data are never exported."""
    credentials = {"api_key": "test-token-value", "password": "test-password-value"}
    entry = Mock()
    entry.entry_id = "test-entry"
    entry.data = {**credentials, "name": "Portainer"}
    entry.options = {"nested": credentials.copy()}
    coordinator = Mock()
    coordinator.data = {"nested": credentials.copy(), "containers": {}}
    hass = Mock()
    hass.data = {"portainer": {entry.entry_id: {"coordinator": coordinator}}}

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"]["name"] == "Portainer"
    for secret in credentials.values():
        assert secret not in repr(diagnostics)
    assert entry.data["api_key"] == credentials["api_key"]
    assert coordinator.data["nested"] == credentials
