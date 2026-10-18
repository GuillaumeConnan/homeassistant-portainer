# Portainer Integration API Documentation

This document provides technical details about the Portainer integration's API usage and data structures.

## Overview

The integration communicates with the Portainer API to retrieve information about endpoints, containers, and stacks. All API calls use the Portainer REST API with authentication via access tokens.

## Authentication

All API requests include authentication headers:
```http
Authorization: Bearer YOUR_ACCESS_TOKEN
```

## API Endpoints Used

### Core Endpoints

#### 1. Get Endpoints
```http
GET /api/endpoints
```

**Purpose**: Retrieve all available Portainer endpoints

**Response Structure**:
```json
[
  {
    "Id": 1,
    "Name": "local",
    "Type": 1,
    "Status": 1,
    "Snapshots": [...]
  }
]
```

**Status Values**:
- `1` = Up/Active
- `2` = Down/Inactive

#### 2. Get Containers (Docker API)
```http
GET /api/endpoints/{endpointId}/docker/containers/json?all=true
```

**Purpose**: Retrieve all containers for a specific endpoint

**Response Structure**:
```json
[
  {
    "Id": "container_id",
    "Names": ["/container_name"],
    "Image": "image_name:tag",
    "State": "running",
    "Ports": [...],
    "Labels": {...}
  }
]
```

#### 3. Inspect Container (Docker API)
```http
GET /api/endpoints/{endpointId}/docker/containers/{containerId}/json
```

**Purpose**: Get detailed container information including health status

**Response Structure**:
```json
{
  "Id": "container_id",
  "State": {
    "Status": "running",
    "Health": {
      "Status": "healthy"
    }
  },
  "HostConfig": {
    "RestartPolicy": {
      "Name": "unless-stopped"
    }
  },
  "NetworkSettings": {...},
  "Mounts": [...],
  "Config": {...}
}
```

## Data Processing

### Container Data Enhancement

The integration processes raw Docker API data and adds computed fields:

#### Basic Container Information
- **Name**: Extracted from `Names[0]` array, with leading `/` removed
- **EndpointId**: Set to the Portainer endpoint ID
- **Environment**: Set to the endpoint name for context

#### Port Information
- **PublishedPorts**: Formatted string of port mappings, sorted lexicographically so Docker response ordering does not cause sensor state changes. IPv4/IPv6 mappings, duplicate entries and internal ports without public mappings are preserved; an empty port list is shown as `"none"`.
- **Format**: `"5432/tcp, 8080->80/tcp"`

#### Mount Information
- **Mounts**: Formatted string of volume mounts
- **Format**: `"/host/path:/container/path, /var/lib/mysql:/var/lib/mysql"`

#### Network Information
- **IPAddress**: Primary IP address from container networks
- **Network**: Network mode (bridge, host, etc.)

### Health Status Processing

Health status is extracted from Docker's health check system:

#### Health Status Values
- `"healthy"` - Container health check passing
- `"unhealthy"` - Container health check failing
- `"starting"` - Container health check in progress
- `"unknown"` - No health check configured or data unavailable
- `"unavailable"` - Container not running (health checks don't apply)

#### Health Data Source
```json
{
  "State": {
    "Health": {
      "Status": "healthy",
      "FailingStreak": 0,
      "Log": [...]
    }
  }
}
```

### Restart Policy Processing

Restart policies are extracted from container host configuration:

#### Policy Values
- `"no"` - Do not restart
- `"always"` - Always restart
- `"on-failure"` - Restart on failure
- `"unless-stopped"` - Restart unless explicitly stopped

## Error Handling

### API Error Scenarios

#### Connection Errors
- **Timeout**: Portainer server not responding
- **HTTP 401**: Invalid or expired access token
- **HTTP 403**: Insufficient permissions
- **HTTP 404**: Endpoint or container not found
- **HTTP 500**: Portainer server internal error

#### Data Processing Errors
- **Malformed JSON**: Invalid API response format
- **Missing Fields**: Expected data not present in response
- **Type Errors**: Data type mismatches

### Graceful Degradation

The integration handles errors gracefully:

1. **API Failures**: Failed inventory or inspection requests fail the entire refresh. The last successful snapshot is preserved, entities become unavailable, and missing-resource repair counters are not advanced.
2. **Offline Endpoints**: An endpoint explicitly reported as down retains its previously discovered containers and stacks as unavailable. This is not treated as resource deletion.
3. **Successful Empty Responses**: Empty inventory lists are valid and can identify genuinely removed resources. Repairs still require three successful scans reporting a missing resource.
4. **Recovery**: The next successful refresh publishes a complete snapshot and restores availability.

Container removal uses `DELETE /api/endpoints/{endpointId}/docker/containers/{containerId}` with Docker query parameters `force` and `v` (anonymous volumes), both defaulting to `false`. Local devices and entities are cleaned up only after a successful response, including `204 No Content`. Failures raise a Home Assistant service error.

## Update Cycle

### Polling Interval
- **Default**: 30 seconds
- **Configurable**: Via `SCAN_INTERVAL` constant
- **Serialized**: API calls run in executor jobs through a shared, locked HTTP session

### Update Process
1. **Fetch Endpoints**: Get all available endpoints
2. **Process Endpoints**: Extract snapshot data for active endpoints
3. **Fetch Containers**: Get containers for each active endpoint
4. **Inspect Containers**: Get detailed information for each container
5. **Process Stacks**: Get stack information
6. **Update Devices**: Refresh Home Assistant device states
7. **Check Repairs**: Update repair issue status

The setup and options selection forms fetch `/api/stacks` only once per form and filter its response by the selected active endpoint IDs. The coordinator also fetches stacks once per refresh and restricts them to selected endpoints.

## Performance Considerations

### API Rate Limiting
- **Serialized Requests**: The session lock serializes API calls
- **Connection Pooling**: Reuse HTTP connections when possible
- **Timeout Management**: 10-second timeout per request

### Memory Management
- **Data Structures**: Efficient dictionary-based storage
- **Cleanup**: Remove stale device data
- **Garbage Collection**: Python handles memory cleanup automatically

### Network Optimization
- **SSL Reuse**: Maintain persistent SSL connections
- **Compression**: Request compressed responses when available
- **Minimal Data**: Only fetch required fields

## Security Considerations

### Access Token Security
- **Token Storage**: Stored securely in Home Assistant configuration
- **Token Scope**: Use minimal required permissions
- **Token Rotation**: Regular token updates recommended
- **Diagnostics**: API keys and passwords are redacted recursively before export

### SSL/TLS Security
- **Certificate Validation**: Enabled by default for new configurations; existing saved settings are preserved. Untrusted self-signed certificates require an explicit opt-out.
- **SSL Version**: Modern TLS versions only
- **Cipher Suites**: Secure cipher suites only

### Network Security
- **API Exposure**: Portainer API should be restricted to Home Assistant IP
- **Firewall Rules**: Limit access to Portainer management interface
- **VPN Consideration**: Use VPN for remote Portainer instances

## Development API

### Testing Endpoints

For development and testing, the integration supports:

#### Mock API Responses
- **Test Data**: Comprehensive test fixtures in `tests/fixtures/`
- **Error Scenarios**: Various failure modes for testing
- **Edge Cases**: Malformed data and missing fields

#### Debug Endpoints
```python
# Enable debug logging to see API requests
logger:
  custom_components.portainer.api: debug
```

### API Response Caching

The integration implements intelligent caching:

- **Device Registry**: Home Assistant manages device state
- **Entity States**: Sensor and button states cached between updates
- **Error State**: Failed devices marked for retry

## Troubleshooting API Issues

### Common API Problems

#### Slow API Responses
```bash
# Check Portainer server performance
# Monitor Docker daemon responsiveness
# Consider reducing container count per endpoint
```

#### Intermittent Failures
```bash
# Check network stability
# Verify Portainer server resources
# Monitor Docker daemon health
```

#### Authentication Issues
```bash
# Verify token validity in Portainer UI
# Check token expiration
# Confirm token permissions
```

### Debug API Calls

Enable debug logging to see detailed API interaction:

```yaml
logger:
  default: info
  logs:
    custom_components.portainer.api: debug
    custom_components.portainer.coordinator: debug
```

This will show:
- API request URLs and methods
- Response status codes
- Data parsing results
- Error conditions and handling

## API Version Compatibility

### Portainer API Versions
- **Supported**: Portainer API v2.x
- **Tested**: CE 2.19.x, BE 2.19.x
- **Compatible**: Docker API v1.43+

### Home Assistant Compatibility
- **Minimum Version**: 2026.9.0
- **Python Version**: 3.11+
- **Dependencies**: None (pure Python implementation)

## Future API Enhancements

### Planned Features
- **WebSocket Support**: Real-time updates instead of polling
- **Batch Operations**: Multiple container operations in single request
- **Advanced Filtering**: More granular container/stack selection
- **Metrics Collection**: Performance and usage metrics

### API Extensibility
- **Plugin Architecture**: Easy to add new API endpoints
- **Custom Sensors**: Support for additional container metrics
- **Webhook Support**: Portainer event-driven updates