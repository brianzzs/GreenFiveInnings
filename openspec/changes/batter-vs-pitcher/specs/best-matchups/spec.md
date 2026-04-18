## ADDED Requirements

### Requirement: Daily best matchups endpoint
The system SHALL expose a `GET /best-matchups/today` endpoint that returns all qualifying batter-vs-pitcher H2H matchups across today's scheduled MLB games.

#### Scenario: Successful response with matchups
- **WHEN** the client calls `GET /best-matchups/today` on a day with scheduled games
- **THEN** the system returns a JSON object with `date`, `total_matchups`, and a `matchups` array sorted by AVG descending

#### Scenario: No games scheduled
- **WHEN** the client calls `GET /best-matchups/today` on a day with no scheduled games
- **THEN** the system returns `{"date": "<date>", "total_matchups": 0, "matchups": []}`

### Requirement: Minimum at-bat filter
The system SHALL exclude any batter-pitcher matchup where the batter has fewer than 2 career at-bats against that pitcher.

#### Scenario: Batter with 1 AB is excluded
- **WHEN** a batter has exactly 1 career AB against the opposing pitcher
- **THEN** that matchup SHALL NOT appear in the response

#### Scenario: Batter with 2 ABs is included
- **WHEN** a batter has exactly 2 career ABs against the opposing pitcher
- **THEN** that matchup SHALL appear in the response

### Requirement: Sort by AVG descending with AB tiebreak
The system SHALL sort matchups by batting average (AVG) from highest to lowest. When two matchups have the same AVG, the matchup with more at-bats SHALL appear first.

#### Scenario: Higher AVG ranked first
- **WHEN** Batter A has .350 AVG (20 AB) and Batter B has .300 AVG (15 AB) against respective pitchers
- **THEN** Batter A appears before Batter B in the list

#### Scenario: Same AVG, more ABs wins tiebreak
- **WHEN** Batter A has .300 AVG (30 AB) and Batter B has .300 AVG (10 AB)
- **THEN** Batter A appears before Batter B

### Requirement: Matchup response structure
Each matchup object SHALL include batter info (id, name, team name, bat side, image URL), pitcher info (id, name, team name, pitch hand), the game ID, and H2H stats (AB, H, HR, RBI, BB, SO, AVG, OPS).

#### Scenario: Complete matchup object
- **WHEN** a qualifying matchup is returned
- **THEN** it contains `batter` (with `id`, `name`, `team_name`, `bat_side`, `image_url`), `pitcher` (with `id`, `name`, `team_name`, `hand`), `game_id`, and `h2h` (with `AB`, `H`, `HR`, `RBI`, `BB`, `SO`, `AVG`, `OPS`)

### Requirement: Lineup resolution with fallback
The system SHALL use confirmed lineups from the game's boxscore when available. When boxscore lineups are not available, the system SHALL fall back to the team's last completed game lineup.

#### Scenario: Confirmed lineup available
- **WHEN** a game's boxscore contains lineup data
- **THEN** the system uses the confirmed lineup batters

#### Scenario: No confirmed lineup, fallback used
- **WHEN** a game's boxscore does not contain lineup data
- **THEN** the system falls back to the last completed game lineup for that team
