# Changelog

## [1.1] — 2024-06-24

### Added
- `cs_get_listener_detail` — full listener config including `beacons` (HTTP Hosts) field
- `beacons` field in `cs_list_listeners` output (distinguish from `host`/stager)
- Listener creation now returns `beacons` field for verification

### Fixed
- Listener info now includes `beacons` field (HTTP Hosts), previously only `host` (stager host)
- Code refactored for readability

### Known Issues
- `listener_create` may not set `beacons` (HTTP Hosts) correctly in headless mode
- `listener_remove` unavailable in CS 4.8 headless
- Multiple listeners on same port causes silent failure

## [1.0] — 2024-06-24

### Added
- Initial release
- 10 MCP tools: beacon/listener CRUD, payload generation, command execution
- CNA code generation via dynamic script + temp file IPC
- `artifact_payload()` confirmed headless-safe (vs `artifact_stageless` which hangs)
- env var configuration (`CS_DIR`, `CS_HOST`, `CS_PORT`, `CS_PASS`)
