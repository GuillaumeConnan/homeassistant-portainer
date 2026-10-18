"""Portainer API."""

import json
import requests
from logging import getLogger
from threading import Lock
from typing import Any, Optional


from homeassistant.core import HomeAssistant

_LOGGER = getLogger(__name__)


# ---------------------------
#   PortainerAPI
# ---------------------------
class PortainerAPI(object):
    """Handle all communication with Portainer."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        api_key: str,
        use_ssl: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize with SSL certificate verification."""
        self._hass = hass
        self._host = host
        self._use_ssl = use_ssl
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._session = requests.Session()
        self._protocol = "https" if self._use_ssl else "http"
        self._url = f"{self._protocol}://{self._host}/api/"
        self._session.headers.update({"X-API-Key": self._api_key})
        self._session.verify = self._verify_ssl
        if not self._verify_ssl and self._use_ssl:
            _LOGGER.warning(
                "SSL certificate verification is disabled for HTTPS connection to %s. "
                "This may pose a security risk. Ensure you trust this host.",
                self._host,
            )
        self.lock = Lock()
        self._connected = False
        self._error = ""

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> bool:
        """Return connected boolean."""
        return self._connected

    # ---------------------------
    #   connection_test
    # ---------------------------
    def connection_test(self) -> tuple:
        """Test connection."""
        result = self.query("endpoints")
        if result is None:
            # Query failed, return the error state
            return False, self._error if self._error else "connection_failed"

        return self._connected, self._error

    # ---------------------------
    #   query
    # ---------------------------
    def query(
        self,
        service: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        timeout: int = 10,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Retrieve data from Portainer."""
        try:
            self.lock.acquire()
        except Exception as e:
            _LOGGER.error("Failed to acquire lock for Portainer API query: %s", e)
            self._error = "lock_error"
            self._connected = False
            return None

        response = None
        try:
            url = f"{self._url}{service}"
            if method == "GET":
                _LOGGER.debug("Portainer API call (GET): %s, params=%s", url, params)
                response = self._session.get(url, params=params, timeout=timeout)
            elif method == "POST":
                _LOGGER.debug("Portainer API call (POST): %s, json=%s", url, params)
                response = self._session.post(url, json=params, timeout=timeout)
            elif method == "PUT":
                response = self._session.put(
                    f"{self._url}{service}", json=params, timeout=timeout
                )
            elif method == "DELETE":
                response = self._session.delete(url, params=params, timeout=timeout)
            else:
                _LOGGER.error("Invalid HTTP method: %s", method)
                self._error = "invalid_method"
                self._connected = False
                return None

            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json() if response.content else None
            self._connected = True
            self._error = ""
            return data
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON response from Portainer API for %s", service)
            self._connected = False
            self._error = "invalid_json"
            return None
        except requests.RequestException as error:
            self._connected = False
            self._error = (
                response.status_code if response is not None else "no_response"
            )
            _LOGGER.warning(
                'Portainer %s unable to fetch data "%s" (%s): %s',
                self._host,
                service,
                self._error,
                error,
            )
            return None
        finally:
            self.lock.release()

    @property
    def error(self):
        """Return error."""
        return self._error

    # ---------------------------
    #   get_all_containers
    # ---------------------------
    def get_all_containers(self) -> list:
        """Get all containers from all known Portainer endpoints."""
        containers = []
        endpoints = self.query("endpoints")
        if not endpoints:
            _LOGGER.warning("No endpoints found or unable to fetch endpoints.")
        else:
            for endpoint in endpoints:
                endpoint_id = endpoint.get("Id")
                if not endpoint_id:
                    continue
                endpoint_containers = self.query(
                    f"endpoints/{endpoint_id}/docker/containers/json"
                )
                if endpoint_containers:
                    containers.extend(endpoint_containers)
        return containers

    # ---------------------------
    #   get_endpoints
    # ---------------------------
    def get_endpoints(self) -> list:
        """Get all endpoints from Portainer."""
        endpoints = self.query("endpoints")
        if not isinstance(endpoints, list) or any(
            not isinstance(endpoint, dict) for endpoint in endpoints
        ):
            raise ValueError(
                f"Unable to fetch endpoints: {self.error or 'invalid response'}"
            )
        # Normalize keys to 'id' and 'name' for config flow
        endpoint_list = []
        for endpoint in endpoints:
            endpoint_id = endpoint.get("Id") or endpoint.get("id")
            endpoint_name = (
                endpoint.get("Name")
                or endpoint.get("name")
                or f"Endpoint {endpoint_id}"
            )
            endpoint_status = endpoint.get("Status")
            if endpoint_id:
                endpoint_list.append(
                    {
                        "id": str(endpoint_id),
                        "name": endpoint_name,
                        "status": endpoint_status,
                    }
                )
        return endpoint_list

    # ---------------------------
    #   get_containers
    # ---------------------------
    def get_containers(self, endpoint_id: str) -> list:
        """Get all containers for a specific endpoint."""
        containers = self.query(f"endpoints/{endpoint_id}/docker/containers/json?all=1")
        if not isinstance(containers, list) or any(
            not isinstance(container, dict) for container in containers
        ):
            raise ValueError(
                f"Unable to fetch containers: {self.error or 'invalid response'}"
            )
        # Normalize keys to 'id', 'name', and add 'status' for config flow
        container_list = []
        for container in containers:
            container_id = container.get("Id") or container.get("id")
            # Remove leading slash from container name if present
            container_name = (
                container.get("Names", [None])[0]
                or container.get("name")
                or f"Container {container_id}"
            )
            if container_name and container_name.startswith("/"):
                container_name = container_name[1:]
            status = container.get("State") or container.get("Status") or "unknown"
            if container_id:
                container_list.append(
                    {
                        "id": str(container_id),
                        "name": container_name,
                        "status": status,
                        "endpoint_id": endpoint_id,
                    }
                )
        return container_list

    # ---------------------------
    #   get_stacks
    # ---------------------------
    def get_stacks(self, endpoint_id: str | None = None) -> list:
        """Get normalized stacks, optionally filtered to one endpoint."""
        all_stacks = self.query("stacks")
        if not isinstance(all_stacks, list) or any(
            not isinstance(stack, dict) for stack in all_stacks
        ):
            raise ValueError(
                f"Unable to fetch stacks: {self.error or 'invalid response'}"
            )
        # Normalize keys to 'id' and 'name' for config flow
        stack_list = []
        for stack in all_stacks:
            if endpoint_id is not None and str(stack.get("EndpointId")) != str(
                endpoint_id
            ):
                continue
            stack_id = stack.get("Id") or stack.get("id")
            stack_name = stack.get("Name") or stack.get("name") or f"Stack {stack_id}"
            if stack_id:
                stack_list.append(
                    {
                        "id": str(stack_id),
                        "name": stack_name,
                        "endpoint_id": str(stack.get("EndpointId")),
                    }
                )
        return stack_list

    # ---------------------------
    #   recreate_container
    # ---------------------------
    def recreate_container(
        self, endpoint_id: str, container_id: str, pull_image: bool = True
    ) -> bool:
        """Recreate a container."""
        _LOGGER.debug(
            "Calling Portainer API to recreate container %s on endpoint %s",
            container_id,
            endpoint_id,
        )
        params = {"pullImage": pull_image} if pull_image else {}
        self.query(
            f"docker/{endpoint_id}/containers/{container_id}/recreate",
            "POST",
            params=params,
            timeout=60,
        )
        _LOGGER.debug("Portainer API call for recreate container completed.")
        return not self._error
