# Changelog

User-visible changes in this independently maintained fork are documented here.
The first release describes the differences from
[cbrosius/homeassistant-portainer v1.1.6](https://github.com/cbrosius/homeassistant-portainer/releases/tag/v1.1.6)
(commit `f7ca729`), not the intermediate development steps or features already
provided by upstream.

This file is the source of truth for GitHub release notes. Each pull request
updates `[Unreleased]`; before publishing, consolidate related entries and move
them into a dated version section.

## [Unreleased]

## [2.0.0] - 2026-10-20

### Added

- Add French translations for the integration configuration, options and services.
- Change the host, access token and TLS settings through Home Assistant's
  reconfiguration flow, and replace rejected tokens through reauthentication.
  New settings are validated before saving, with translated connection errors.

### Changed

- Require Home Assistant 2026.9.0 or newer.
- Establish independent releases, documentation and issue tracking for this fork.
- Fetch stacks once per setup/options selection form and filter them locally by
  selected, reachable endpoints instead of repeating the same request.

### Fixed

- Preserve the last complete inventory after API failures and retain cached
  containers and stacks while their endpoint is offline. Affected entities become
  unavailable instead of being reported as deleted; failed requests no longer
  advance missing-resource repair counters.
- Preserve saved endpoint, container and stack selections when resources are
  temporarily absent or connection settings change. Accept historical container
  selection identifiers and clean up deselected devices only after the final
  options form is submitted, without affecting unrelated devices or deleting
  resources in Portainer.
- Publish entity unavailability immediately when a resource disappears from a
  successful inventory refresh.
- Discover sensors and action buttons for selected resources that appear after
  startup, without requiring an integration reload or creating duplicate entities.
- Fix container platform setup and parent-device relationships by resolving
  endpoint devices through the coordinator and using their registered device IDs.
- Update device ownership, service-target and repair lookups for current
  Home Assistant registry APIs, keeping devices scoped to their integration entry.
- Avoid duplicate reloads and related deprecation warnings after reconfiguration
  or reauthentication.
- Report failures consistently for container and stack actions, recreation and
  action buttons. Multi-device services attempt all targets and report any failures
  instead of silently succeeding.
- Make the container `remove` action delete the actual container through Docker's
  DELETE endpoint. Expose forced removal and anonymous-volume removal in the
  service UI; named volumes are not removed. Home Assistant devices and entities
  are cleaned up only after remote deletion succeeds.
- Stabilize the ordering of published container ports to avoid unnecessary
  Home Assistant state changes.
- Preserve explicit SSL settings when retrying integration setup.

### Security

- Redact API keys, as well as passwords, recursively from exported diagnostics.
- Mask access-token inputs without prefilling or echoing secrets after errors.
  An empty token during reconfiguration keeps the saved token; initial setup and
  reauthentication require an explicit token.
- Enable TLS certificate verification by default for new configurations and stop
  suppressing TLS warnings globally. Existing saved settings are unchanged.

### Migration notes

- Home Assistant 2026.9.0 or newer is required. This fork replaces the upstream
  integration using the same `portainer` domain; they cannot run side by side.
- Existing resource selections remain supported and are normalized automatically
  when integration options are saved; no manual reselection is required.
- Automations now receive errors for failed actions beyond container removal.
  Review any scripts that previously relied on these failures being ignored.
- New setups using an untrusted self-signed certificate must either use a
  certificate trusted by Home Assistant or explicitly disable certificate
  verification for a trusted connection.
- The `remove` service action deletes the actual container, not just its
  Home Assistant device. Both `force` and `remove_volumes` default to `false`.
