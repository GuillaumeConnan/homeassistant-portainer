"""Config flow to configure Portainer."""

from __future__ import annotations

from logging import getLogger
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_SSL,
    DEFAULT_SSL_VERIFY,
    DOMAIN,
    # feature switch
    CONF_FEATURE_HEALTH_CHECK,
    DEFAULT_FEATURE_HEALTH_CHECK,
    CONF_FEATURE_RESTART_POLICY,
    DEFAULT_FEATURE_RESTART_POLICY,
    CONF_FEATURE_USE_ACTION_BUTTONS,
    DEFAULT_FEATURE_USE_ACTION_BUTTONS,
)

from .api import PortainerAPI
from .helper import normalize_container_selection

_LOGGER = getLogger(__name__)


def _connection_error(error) -> str:
    """Map API failures to translated form errors."""
    return "invalid_auth" if str(error) in ("401", "403") else "cannot_connect"


# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass):
    """Return a set of configured instances."""
    return {
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


# ---------------------------
#   PortainerConfigFlow
# ---------------------------
class PortainerConfigFlow(ConfigFlow, domain=DOMAIN):
    """PortainerConfigFlow class."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Occurs when a previous entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: collect Portainer credentials and test connection."""
        errors = {}
        if user_input is not None:
            # Check if instance with this name already exists
            if user_input[CONF_NAME] in configured_instances(self.hass):
                errors["base"] = "name_exists"
            elif not user_input.get(CONF_API_KEY):
                errors[CONF_API_KEY] = "required_token"
            else:
                # Test connection
                self.api = await self.hass.async_add_executor_job(
                    PortainerAPI,
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_API_KEY],
                    user_input[CONF_SSL],
                    user_input[CONF_VERIFY_SSL],
                )
                conn, errorcode = await self.hass.async_add_executor_job(
                    self.api.connection_test
                )
                if not conn:
                    errors["base"] = _connection_error(errorcode)
                    _LOGGER.error("Portainer connection error (%s)", errorcode)

            # Save instance and proceed if no errors
            if not errors:
                self.options = user_input
                return await self.async_step_endpoints()

            return self._show_config_form(user_input=user_input, errors=errors)

        # Show the initial form
        return self._show_config_form(
            user_input={
                CONF_NAME: DEFAULT_DEVICE_NAME,
                CONF_HOST: DEFAULT_HOST,
                CONF_API_KEY: "",
                CONF_SSL: DEFAULT_SSL,
                CONF_VERIFY_SSL: DEFAULT_SSL_VERIFY,
            },
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Replace revoked credentials without changing resource selections."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Validate replacement credentials before updating the existing entry."""
        return await self._async_step_connection("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Allow changing the host, token and TLS settings."""
        return await self._async_step_connection("reconfigure", user_input)

    async def _async_step_connection(self, step_id, user_input) -> FlowResult:
        entry = (
            self._get_reauth_entry()
            if step_id == "reauth_confirm"
            else self._get_reconfigure_entry()
        )
        errors = {}
        if (
            user_input is not None
            and step_id == "reauth_confirm"
            and not user_input.get(CONF_API_KEY)
        ):
            return self._show_config_form(
                user_input, {CONF_API_KEY: "required_token"}, step_id=step_id
            )
        if user_input is not None:
            connection = dict(user_input)
            if step_id == "reconfigure" and not connection.get(CONF_API_KEY):
                connection[CONF_API_KEY] = entry.data[CONF_API_KEY]
            api = await self.hass.async_add_executor_job(
                PortainerAPI,
                self.hass,
                connection[CONF_HOST],
                connection[CONF_API_KEY],
                connection[CONF_SSL],
                connection[CONF_VERIFY_SSL],
            )
            connected, error = await self.hass.async_add_executor_job(
                api.connection_test
            )
            if connected:
                return self.async_update_and_abort(entry, data_updates=connection)
            errors["base"] = _connection_error(error)
        return self._show_config_form(
            user_input if user_input is not None else entry.data,
            errors,
            step_id=step_id,
        )

    def _show_config_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, Any] | None = None,
        *,
        step_id: str = "user",
    ) -> FlowResult:
        """Show the configuration form."""
        user_input = user_input or {}
        schema = {
            vol.Required(
                CONF_NAME,
                default=str(user_input.get(CONF_NAME, DEFAULT_DEVICE_NAME)),
            ): str,
            vol.Required(
                CONF_HOST, default=str(user_input.get(CONF_HOST, DEFAULT_HOST))
            ): str,
            (
                vol.Optional(CONF_API_KEY)
                if step_id == "reconfigure"
                else vol.Required(CONF_API_KEY)
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(CONF_SSL, default=user_input.get(CONF_SSL, DEFAULT_SSL)): bool,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(CONF_VERIFY_SSL, DEFAULT_SSL_VERIFY),
            ): bool,
        }
        if step_id != "user":
            schema = {
                key: value for key, value in schema.items() if key.schema != CONF_NAME
            }
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_endpoints(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to select Portainer endpoints to import."""
        errors = {}
        if user_input is not None:
            if not user_input.get("endpoints"):
                errors["base"] = "no_endpoints_selected"
            else:
                # Save selected endpoints and continue
                self.options["endpoints"] = user_input["endpoints"]
                return await self.async_step_select_items()

        # Fetch endpoints from Portainer API
        try:
            endpoints = await self.hass.async_add_executor_job(self.api.get_endpoints)
        except Exception as exc:
            _LOGGER.error("Failed to fetch endpoints: %s", exc)
            return self.async_show_form(
                step_id="endpoints",
                data_schema=vol.Schema({}),
                errors={"base": "endpoint_fetch_failed"},
            )

        endpoint_options = {str(ep["id"]): ep["name"] for ep in endpoints}
        if not endpoint_options:
            errors["base"] = "no_endpoints_found"
            return self.async_show_form(
                step_id="endpoints",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="endpoints",
            data_schema=vol.Schema(
                {
                    vol.Required("endpoints", default=[]): cv.multi_select(
                        endpoint_options
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_select_items(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step to select containers and stacks from selected endpoints."""
        if user_input is not None:
            # Save selected containers and stacks, finish config flow
            self.options["containers"] = user_input.get("containers", [])
            self.options[CONF_FEATURE_USE_ACTION_BUTTONS] = user_input.get(
                CONF_FEATURE_USE_ACTION_BUTTONS, True
            )
            self.options["stacks"] = user_input.get("stacks", [])

            # Set default feature values
            self.options[CONF_FEATURE_HEALTH_CHECK] = DEFAULT_FEATURE_HEALTH_CHECK
            self.options[CONF_FEATURE_RESTART_POLICY] = DEFAULT_FEATURE_RESTART_POLICY

            return self.async_create_entry(
                title=self.options[CONF_NAME], data=self.options
            )

        # Fetch containers and stacks for selected endpoints
        try:
            containers = []
            stacks = []
            endpoints = await self.hass.async_add_executor_job(self.api.get_endpoints)
            active_endpoint_ids = set()
            for endpoint in endpoints:
                if (
                    str(endpoint["id"]) in self.options["endpoints"]
                    and endpoint["status"] == 1
                ):
                    active_endpoint_ids.add(str(endpoint["id"]))
                    containers += await self.hass.async_add_executor_job(
                        self.api.get_containers, endpoint["id"]
                    )
            if active_endpoint_ids:
                stacks = [
                    stack
                    for stack in await self.hass.async_add_executor_job(
                        self.api.get_stacks
                    )
                    if str(stack["endpoint_id"]) in active_endpoint_ids
                ]
        except Exception as exc:
            _LOGGER.exception("Failed to fetch containers/stacks: %s", exc)
            return self.async_abort(reason="item_fetch_failed")

        # Show status in container name
        container_options = {
            f"{c['endpoint_id']}_{c['name']}": f"{c['name']} [{c['status']}]"
            for c in containers
        }
        _LOGGER.debug("Config flow - Created container options: %s", container_options)
        stack_options = {str(s["id"]): s["name"] for s in stacks}

        schema_dict = {}
        if container_options:
            schema_dict[vol.Optional("containers", default=[])] = cv.multi_select(
                container_options
            )
        if stack_options:
            schema_dict[vol.Optional("stacks", default=[])] = cv.multi_select(
                stack_options
            )
        schema_dict[
            vol.Optional(
                CONF_FEATURE_USE_ACTION_BUTTONS,
                default=DEFAULT_FEATURE_USE_ACTION_BUTTONS,
            )
        ] = bool
        return self.async_show_form(
            step_id="select_items",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "containers": ", ".join(container_options.values()),
                "stacks": ", ".join(stack_options.values()),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlow()


class PortainerOptionsFlow(OptionsFlow):
    """Handle options flow for Portainer integration, including endpoint/container/stack selection."""

    def _current_options(self):
        return {**self.config_entry.data, **self.config_entry.options}

    def _normalize_container(self, identifier):
        return normalize_container_selection(
            str(identifier),
            self.config_entry.entry_id,
            self.config_entry.data.get(CONF_NAME, ""),
        )

    def _api(self):
        data = self.config_entry.data
        return PortainerAPI(
            self.hass,
            data[CONF_HOST],
            data[CONF_API_KEY],
            data[CONF_SSL],
            data[CONF_VERIFY_SSL],
        )

    async def async_step_init(self, user_input=None):
        """Stage endpoint choices without modifying the registries."""
        errors = {}
        if user_input is not None:
            if user_input.get("endpoints"):
                self.options = dict(self.config_entry.options)
                self.options["endpoints"] = [str(e) for e in user_input["endpoints"]]
                return await self.async_step_select_items()
            errors["base"] = "no_endpoints_selected"

        current = [str(e) for e in self._current_options().get("endpoints", [])]
        try:
            endpoints = await self.hass.async_add_executor_job(
                self._api().get_endpoints
            )
        except Exception as exc:
            _LOGGER.error("Failed to fetch endpoints: %s", exc)
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "endpoint_fetch_failed"},
            )
        endpoint_options = {str(ep["id"]): ep["name"] for ep in endpoints}
        for endpoint_id in current:
            endpoint_options.setdefault(endpoint_id, endpoint_id)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("endpoints", default=current): cv.multi_select(
                        endpoint_options
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "endpoints": ", ".join(endpoint_options.values())
            },
        )

    def _remove_deselected_devices(self, new_options):
        """Remove only exact, typed identifiers after the final submission."""
        current = self._current_options()
        entry_id = self.config_entry.entry_id
        removed_endpoints = set(map(str, current.get("endpoints", []))) - set(
            new_options["endpoints"]
        )
        removed_containers = {
            self._normalize_container(cid) for cid in current.get("containers", [])
        } - set(new_options["containers"])
        removed_stacks = set(map(str, current.get("stacks", []))) - set(
            new_options["stacks"]
        )
        registry = dr.async_get(self.hass)
        entities = er.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(registry, entry_id)
        identifiers = {
            "Endpoint": {f"{eid}_{entry_id}" for eid in removed_endpoints},
            "Container": {f"{entry_id}_{cid}" for cid in removed_containers},
            "Stack": {f"{entry_id}_stack_{sid}" for sid in removed_stacks},
        }
        removed_parents = {
            device.id
            for device in devices
            if device.model == "Endpoint"
            and any(
                (DOMAIN, identifier) in device.identifiers
                for identifier in identifiers["Endpoint"]
            )
        }
        for device in devices:
            if device.config_entry_id != entry_id:
                continue
            if device.model not in identifiers or not any(
                domain == DOMAIN for domain, _ in device.identifiers
            ):
                continue
            if device.via_device_id not in removed_parents and not any(
                (DOMAIN, identifier) in device.identifiers
                for identifier in identifiers[device.model]
            ):
                continue
            for entity in er.async_entries_for_device(
                entities, device.id, include_disabled_entities=True
            ):
                if entity.config_entry_id == entry_id:
                    entities.async_remove(entity.entity_id)
            registry.async_remove_device(device.id)

    async def async_step_select_items(self, user_input=None):
        """Keep saved resources selectable even when inventory is unavailable."""
        current = self._current_options()
        options = getattr(self, "options", dict(self.config_entry.options))
        selected_endpoints = set(
            map(str, options.get("endpoints", current.get("endpoints", [])))
        )
        if user_input is not None:
            options["endpoints"] = sorted(selected_endpoints)
            options["containers"] = list(
                dict.fromkeys(
                    self._normalize_container(cid)
                    for cid in user_input.get("containers", [])
                    if self._normalize_container(cid).split("_", 1)[0]
                    in selected_endpoints
                )
            )
            options["stacks"] = [str(sid) for sid in user_input.get("stacks", [])]
            options[CONF_FEATURE_USE_ACTION_BUTTONS] = user_input.get(
                CONF_FEATURE_USE_ACTION_BUTTONS,
                current.get(
                    CONF_FEATURE_USE_ACTION_BUTTONS, DEFAULT_FEATURE_USE_ACTION_BUTTONS
                ),
            )
            self._remove_deselected_devices(options)
            return self.async_create_entry(title="", data=options)

        try:
            api = self._api()
            containers = []
            stacks = []
            endpoints = await self.hass.async_add_executor_job(api.get_endpoints)
            active_endpoint_ids = set()
            for endpoint in endpoints:
                if (
                    str(endpoint["id"]) in selected_endpoints
                    and endpoint["status"] == 1
                ):
                    active_endpoint_ids.add(str(endpoint["id"]))
                    containers += await self.hass.async_add_executor_job(
                        api.get_containers, endpoint["id"]
                    )
            if active_endpoint_ids:
                stacks = await self.hass.async_add_executor_job(api.get_stacks)
        except Exception as exc:
            _LOGGER.exception("Failed to fetch containers/stacks: %s", exc)
            return self.async_abort(reason="item_fetch_failed")

        container_options = {
            f"{c['endpoint_id']}_{c['name']}": f"{c['name']} [{c['status']}]"
            for c in containers
        }
        stack_options = {
            str(s["id"]): s["name"]
            for s in stacks
            if str(s["endpoint_id"]) in active_endpoint_ids
        }
        current_containers = list(
            dict.fromkeys(
                self._normalize_container(cid)
                for cid in current.get("containers", [])
                if self._normalize_container(cid).split("_", 1)[0] in selected_endpoints
            )
        )
        stack_endpoints = {str(s["id"]): str(s["endpoint_id"]) for s in stacks}
        coordinator = (
            self.hass.data.get(DOMAIN, {})
            .get(self.config_entry.entry_id, {})
            .get("coordinator")
        )
        if coordinator is not None:
            stack_endpoints.update(
                {
                    str(sid): str(stack["EndpointId"])
                    for sid, stack in coordinator.data.get("stacks", {}).items()
                }
            )
        registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        )
        endpoint_devices = {
            device.id: eid
            for device in devices
            for eid in current.get("endpoints", [])
            if device.model == "Endpoint"
            and (DOMAIN, f"{eid}_{self.config_entry.entry_id}") in device.identifiers
        }
        for device in devices:
            if device.model == "Stack" and device.via_device_id in endpoint_devices:
                for domain, identifier in device.identifiers:
                    prefix = f"{self.config_entry.entry_id}_stack_"
                    if domain == DOMAIN and identifier.startswith(prefix):
                        stack_endpoints[identifier[len(prefix) :]] = str(
                            endpoint_devices[device.via_device_id]
                        )
        current_stacks = [
            str(sid)
            for sid in current.get("stacks", [])
            if str(sid) not in stack_endpoints
            or stack_endpoints[str(sid)] in selected_endpoints
        ]
        for cid in current_containers:
            container_options.setdefault(cid, cid)
        for sid in current_stacks:
            stack_options.setdefault(sid, sid)
        return self.async_show_form(
            step_id="select_items",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "containers", default=current_containers
                    ): cv.multi_select(container_options),
                    vol.Optional("stacks", default=current_stacks): cv.multi_select(
                        stack_options
                    ),
                    vol.Optional(
                        CONF_FEATURE_USE_ACTION_BUTTONS,
                        default=current.get(
                            CONF_FEATURE_USE_ACTION_BUTTONS,
                            DEFAULT_FEATURE_USE_ACTION_BUTTONS,
                        ),
                    ): bool,
                }
            ),
            description_placeholders={
                "containers": ", ".join(container_options.values()),
                "stacks": ", ".join(stack_options.values()),
            },
        )
