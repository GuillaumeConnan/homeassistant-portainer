# Changelog

All notable changes in this fork are documented here. This file is the source of
truth for GitHub release notes. Each pull request updates `[Unreleased]`; before
publishing, move its entries into a dated version section.

## [Unreleased]

### Added

- Add French translations for the integration configuration, options and services.
- Add reauthentication for rejected access tokens and a reconfiguration flow for
  changing the host, token and TLS settings. Validate the connection before saving,
  preserve resource selections and provide translated connection errors.
- Expose container removal, forced removal and anonymous-volume removal in the
  Home Assistant service UI. Named volumes are not removed.
- Publish release notes directly from the matching dated section in this
  changelog, with a full GitHub comparison link when a previous version tag exists.
  Missing, duplicate or empty release sections stop the release workflow before
  the integration archive is uploaded.

### Changed

- Require Home Assistant 2026.9.0 or newer.
- Align development dependencies, tox and CI with Home Assistant 2026.9.0 and
  Python 3.14.2 or newer. Test both the minimum and latest compatible Home Assistant
  releases in CI, raise code-quality tool minimum versions and remove unused test
  dependencies.
- Document development with a local Python virtual environment and ignore local
  editor settings, virtual environments, test caches and coverage output.
- Establish independent releases, documentation and issue tracking for this fork.
- Fetch stacks once per setup/options selection form and filter them locally by
  selected, reachable endpoints instead of repeating the same request.
- Preserve the last complete inventory when an API request fails, and mark
  entities unavailable until a successful refresh.
- Retain cached containers and stacks as unavailable while their endpoint is
  offline, without reporting them as deleted.

### Fixed

- Mask access-token inputs without prefilling or echoing secrets after errors.
  Keep the saved token when reconfiguration leaves the field empty, and require
  an explicit token for initial setup and reauthentication.
- Use single config-entry device ownership when removing deselected devices and
  resolving service targets, replacing `DeviceEntry.config_entries` before its
  removal in Home Assistant 2027.10.
- Resolve endpoint devices through the coordinator's Home Assistant instance
  during entity migration, before sensors and buttons have been added to a
  platform, so selecting a container no longer breaks platform setup.
- Let the existing update listener reload the integration after reconfiguration
  or reauthentication, avoiding duplicate reloads and the Home Assistant 2026.12
  deprecation warning.
- Scope device identifier lookups to the config entry and resolve repair targets
  by their saved registry ID, replacing device lookups removed in Home Assistant
  2027.8.
- Preserve saved endpoint, container and stack selections when resources are
  offline or temporarily absent, including selections stored before the first
  options update. Normalize container selection identifiers while accepting
  historical integration-name and config-entry-ID formats.
- Defer device cleanup until the final options form is submitted. Match exact
  identifiers and device types so deselecting stack or endpoint `1` cannot remove
  unrelated devices such as `10`. Deselecting resources does not delete them in
  Portainer.
- Publish entity unavailability immediately when a resource disappears from a
  successful inventory refresh.
- Discover sensors and action buttons for selected resources that appear after
  startup, without requiring an integration reload or creating duplicate entities.
- Report failures consistently for container and stack actions, recreation and
  action buttons. Multi-device services attempt all targets and report any failures
  instead of silently succeeding.
- Stabilize the ordering of published container ports to avoid unnecessary
  Home Assistant state changes.
- Use the registered endpoint device ID for parent-device relationships.
- Prevent failed API requests from advancing missing-resource repair counters.
  Successful empty inventories still detect genuinely removed resources.
- Delete containers through Docker's DELETE endpoint and forward `force` and
  anonymous-volume removal options. Clean up Home Assistant devices and entities
  only after remote deletion succeeds, and report deletion failures as service errors.
- Preserve explicit SSL settings when retrying integration setup.
- Restore and extend automated integration tests and remove the inherited
  upstream SonarCloud workflow.
- Apply pytest configuration correctly and adapt options-flow tests to
  Home Assistant's read-only config-entry lookup.

### Removed

- Remove the shared VS Code launch configuration and dev container configuration.
  Developers can continue using their preferred editor or container setup locally.

### Security

- Redact API keys, as well as passwords, recursively from exported diagnostics.
- Enable TLS certificate verification by default for new configurations and stop
  suppressing TLS warnings globally. Existing saved settings are unchanged.

### Migration notes

- Contributors need Python 3.14.2 or newer. Recreate older development environments
  and install `requirements-test.txt`; code-quality tools are installed separately
  through tox or CI.
- Existing resource selections remain supported and are normalized automatically
  when integration options are saved; no manual reselection is required.
- Automations now receive errors for failed actions beyond container removal.
  Review any scripts that previously relied on these failures being ignored.
- New setups using an untrusted self-signed certificate must either use a
  certificate trusted by Home Assistant or explicitly disable certificate
  verification for a trusted connection.
- The `remove` service action deletes the actual container, not just its
  Home Assistant device. Both `force` and `remove_volumes` default to `false`.
- Previously published upstream releases are not reconstructed here. Release
  entries below will describe releases of this independently maintained fork.
