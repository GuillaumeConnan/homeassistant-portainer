# Changelog

All notable changes in this fork are documented here. This file is the source of
truth for GitHub release notes. Each pull request updates `[Unreleased]`; before
publishing, move its entries into a dated version section.

## [Unreleased]

### Added

- Add French translations for the integration configuration, options and services.
- Expose container removal, forced removal and anonymous-volume removal in the
  Home Assistant service UI. Named volumes are not removed.
- Publish release notes directly from the matching dated section in this
  changelog, with a full GitHub comparison link when a previous version tag exists.
  Missing, duplicate or empty release sections stop the release workflow before
  the integration archive is uploaded.

### Changed

- Require Home Assistant 2026.9.0 or newer.
- Establish independent releases, documentation and issue tracking for this fork.
- Fetch stacks once per setup/options selection form and filter them locally by
  selected, reachable endpoints instead of repeating the same request.
- Preserve the last complete inventory when an API request fails, and mark
  entities unavailable until a successful refresh.
- Retain cached containers and stacks as unavailable while their endpoint is
  offline, without reporting them as deleted.

### Fixed

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

### Security

- Redact API keys, as well as passwords, recursively from exported diagnostics.
- Enable TLS certificate verification by default for new configurations and stop
  suppressing TLS warnings globally. Existing saved settings are unchanged.

### Migration notes

- New setups using an untrusted self-signed certificate must either use a
  certificate trusted by Home Assistant or explicitly disable certificate
  verification for a trusted connection.
- The `remove` service action deletes the actual container, not just its
  Home Assistant device. Both `force` and `remove_volumes` default to `false`.
- Previously published upstream releases are not reconstructed here. Release
  entries below will describe releases of this independently maintained fork.
