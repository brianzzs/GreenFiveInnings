## ADDED Requirements

### Requirement: Shared aiohttp session management
The system SHALL provide a singleton `aiohttp.ClientSession` that is shared across all HTTP calls within a worker process. The session SHALL be lazily initialized on first access and closed on application teardown.

#### Scenario: Session is reused across requests
- **WHEN** multiple HTTP calls are made within the same worker
- **THEN** all calls use the same `aiohttp.ClientSession` instance

#### Scenario: Session is closed on teardown
- **WHEN** the Flask application shuts down
- **THEN** the `aiohttp.ClientSession` is properly closed, releasing all connections

#### Scenario: Session creation outside request context
- **WHEN** code needs an HTTP session outside of a Flask request (e.g., tests, CLI)
- **THEN** a standalone session factory SHALL be available

### Requirement: All MLB API direct calls use aiohttp
The system SHALL use `aiohttp` for all direct HTTP calls to MLB Stats API endpoints, including but not limited to: game data, player stats (with season), H2H stats, standings, player info with stats, and player stat data.

#### Scenario: Player H2H stats fetched asynchronously
- **WHEN** the comparison endpoint requests H2H stats for ~20 batter-pitcher pairs
- **THEN** all H2H HTTP calls execute concurrently via `aiohttp`, not via `asyncio.to_thread`

#### Scenario: Standings fetched asynchronously
- **WHEN** standings data is requested
- **THEN** the HTTP call to the MLB standings endpoint uses `aiohttp` directly

#### Scenario: Player season stats fetched asynchronously
- **WHEN** pitcher season stats are fetched with a specific season parameter
- **THEN** the direct MLB API call uses `aiohttp`, not the `requests` library

### Requirement: statsapi library calls remain wrapped in asyncio.to_thread
The system SHALL continue using `asyncio.to_thread` for calls to the third-party `statsapi` library functions (`statsapi.get`, `statsapi.schedule`, `statsapi.lookup_player`, `statsapi.player_stats`, `statsapi.player_stat_data`) since they are synchronous-only.

#### Scenario: Schedule fetched via statsapi
- **WHEN** schedule data is fetched using the `statsapi.schedule` function
- **THEN** it is called inside `asyncio.to_thread` to avoid blocking the event loop

### Requirement: Connection pooling and timeouts
The shared `aiohttp.ClientSession` SHALL be configured with a connection pool limit of 20 concurrent connections and a total request timeout of 10 seconds, matching the current `MLB_API_TIMEOUT`.

#### Scenario: Timeout enforced on slow MLB API responses
- **WHEN** an MLB API call takes longer than 10 seconds
- **THEN** the request is cancelled and an error is returned

#### Scenario: Connection pool prevents resource exhaustion
- **WHEN** more than 20 concurrent HTTP requests are in flight
- **THEN** excess requests wait for an available connection rather than opening unlimited sockets
