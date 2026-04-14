## ADDED Requirements

### Requirement: Parallel weather fetches for park factors
The system SHALL fetch weather forecasts for all games concurrently using `asyncio.gather()` rather than sequentially iterating over the game list.

#### Scenario: All weather calls run concurrently
- **WHEN** the `/park-factors` endpoint processes 15 games
- **THEN** all 15 weather API calls execute in parallel, bounded only by the aiohttp connection pool limit

#### Scenario: Individual weather failure does not block others
- **WHEN** one weather API call fails or times out
- **THEN** the remaining weather calls complete normally and the failed game uses baseline stadium data without weather effects

### Requirement: Park-factors endpoint responds under 5 seconds
The `/park-factors` endpoint SHALL respond in under 5 seconds for a cold cache request on a typical day with ~15 games.

#### Scenario: Cold cache response time
- **WHEN** the TTL cache is empty and ~15 games are scheduled
- **THEN** the full `/park-factors` response is returned in under 5 seconds

#### Scenario: Warm cache response time
- **WHEN** the TTL cache contains the current day's park factors
- **THEN** the `/park-factors` response is returned in under 500ms

### Requirement: Weather errors are handled per-game
The system SHALL handle weather fetch failures gracefully on a per-game basis. A game with failed weather data SHALL still appear in the response with stadium-baseline factors only.

#### Scenario: Weather API returns error for one venue
- **WHEN** the Open-Meteo API fails for one park but succeeds for others
- **THEN** the failed game appears in the response with `weather: null` fields and `traits: ["weather_unavailable"]`, while all other games include full weather data
