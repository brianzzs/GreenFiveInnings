# Park Factors Feature Plan

## Goal
Build a new backend endpoint that returns **today's MLB park/weather factors** for frontend cards.

This feature should feel similar to Ballpark Pal's park factors, but scoped to a **rules-based v1** focused on the two most important betting outputs:

- **Runs impact %**
- **Home run impact %**

The endpoint should also include the key weather inputs that drive those scores:

- wind
- max temperature
- min temperature
- precipitation probability

We do **not** need a long editorial write-up. Instead, we will return:

- a compact slate-level highlights object
- a short per-game summary
- card-friendly structured data for the frontend

---

## Final Decisions From Planning

- **Endpoint scope:** today only
- **Endpoint name:** `GET /park-factors`
- **Games included:** pregame scheduled + in-progress
- **Model version:** rules-based v1
- **Weather provider:** free provider, recommended **Open-Meteo**
- **Primary outputs:** runs impact and HR impact
- **Narrative output:** short per-game summary, no long historical/article write-up
- **Weather timing:** use **first-pitch weather** even for in-progress games
- **Park metadata:** local maintained stadium dataset
- **Roof assumption:** if weather is bad, assume retractable roof is closed
- **Pressure:** omitted from v1 unless later proven necessary
- **Frontend target:** card list

---

## Endpoint Contract

### Route

`GET /park-factors`

### Response shape

```json
{
  "date": "2026-04-10",
  "generated_at": "2026-04-10T18:05:00Z",
  "highlights": {
    "best_hitter_environment": {
      "game_id": 1,
      "label": "LAA @ CIN",
      "venue": "Great American Ball Park",
      "runs_pct": 9
    },
    "most_pitcher_friendly": {
      "game_id": 2,
      "label": "PIT @ CHC",
      "venue": "Wrigley Field",
      "runs_pct": -17
    },
    "warmest_game": {
      "game_id": 3,
      "label": "ATL vs NYM",
      "temperature_f": 74
    },
    "coldest_game": {
      "game_id": 4,
      "label": "PIT @ CHC",
      "temperature_f": 46
    },
    "windiest_game": {
      "game_id": 5,
      "label": "SF @ BAL",
      "wind_speed_mph": 14
    }
  },
  "games": [
    {
      "game_id": 123,
      "status": "Scheduled",
      "game_datetime": "2026-04-10T18:20:00Z",
      "matchup": {
        "away_team_id": 134,
        "away_team_name": "Pittsburgh Pirates",
        "home_team_id": 112,
        "home_team_name": "Chicago Cubs"
      },
      "venue": {
        "name": "Wrigley Field",
        "city": "Chicago",
        "roof_type": "open",
        "roof_status_assumption": "open"
      },
      "weather": {
        "game_temp_f": 47,
        "temp_min_f": 43,
        "temp_max_f": 50,
        "wind_speed_mph": 9,
        "wind_gust_mph": 14,
        "wind_direction_degrees": 25,
        "wind_direction_label": "in",
        "precipitation_probability_pct": 10
      },
      "factors": {
        "stadium_runs_pct": -2,
        "weather_runs_pct": -14,
        "combined_runs_pct": -16,
        "stadium_hr_pct": 2,
        "weather_hr_pct": -18,
        "combined_hr_pct": -16,
        "rating": "strong_pitcher"
      },
      "traits": ["cold", "wind_in", "wind_sensitive_park"],
      "summary": "Cold temperatures and wind blowing in create a pitcher-friendly run environment."
    }
  ]
}
```

### Notes

- `games` is optimized for a **card list**.
- `highlights` gives the frontend quick slate-level callouts without requiring a long write-up.
- `rating` will support a color badge on the card.

---

## Out of Scope for V1

These items are intentionally excluded from the first implementation:

- historical/backtested park model
- 1B / 2B / 3B breakdowns
- pressure-based flight modeling
- live/current weather updates during in-progress games
- article-style generated paragraph recap
- date parameter support

We can add those later once the v1 endpoint is stable.

---

## Data Sources

### 1. MLB schedule data
Use the existing MLB stats integration to fetch today's slate.

Likely source:
- `app/clients/mlb_stats_client.py`

Important behavior for this feature:
- include **Scheduled**, **Pre-Game**, **Warmup**, **In Progress**, **Delayed Start**, **Delayed** if returned
- exclude **Final**, **Game Over**, **Completed Early**, **Postponed**, **Cancelled**, **Suspended**

### 2. Weather data
Use **Open-Meteo** for free forecast data.

Recommended fields:
- hourly:
  - `temperature_2m`
  - `wind_speed_10m`
  - `wind_gusts_10m`
  - `wind_direction_10m`
  - `precipitation_probability`
- daily:
  - `temperature_2m_max`
  - `temperature_2m_min`

Why Open-Meteo:
- free
- no API key required
- enough forecast detail for first-pitch weather
- easy request/response format

### 3. Local park metadata
Create a local dataset for all MLB home parks.

Each park entry should include:
- `home_team_id`
- `venue_name`
- `city`
- `state`
- `lat`
- `lon`
- `roof_type` (`open`, `fixed_dome`, `retractable`)
- `field_orientation_deg` (home plate -> center field bearing)
- `wind_receptivity`
- `park_runs_pct`
- `park_hr_pct`

This dataset will be manually curated and versioned in the repo.

---

## Recommended File Structure

### New files

- `app/api/park_factors.py`
- `app/services/park_factor_service.py`
- `app/clients/weather_client.py`
- `app/data/__init__.py`
- `app/data/mlb_parks.py`
- `tests/test_park_factors.py`

### Existing files to update

- `app/__init__.py`

---

## Implementation Design

## 1. API layer

### File
`app/api/park_factors.py`

### Responsibility
- expose Flask blueprint
- define `GET /park-factors`
- call the service
- return JSON

### Route behavior
- no params in v1
- returns today's slate only
- returns `[]` if there are no eligible games
- avoids business logic inside the route

---

## 2. Service layer

### File
`app/services/park_factor_service.py`

### Responsibility
Build the full response payload.

### Main flow
1. get today's date via `season_context.reference_date()`
2. fetch today's MLB schedule directly from the client
3. filter to games we want to show
4. map each game's `home_team_id` to park metadata
5. fetch weather forecast for that park
6. select the forecast hour nearest first pitch
7. determine roof status assumption
8. calculate stadium-only and weather-only impacts
9. calculate combined runs/hr impacts
10. assign traits, rating, and short summary
11. build slate highlights
12. cache the result and return it

### Suggested public function

```python
def get_today_park_factors() -> dict:
    ...
```

### Suggested internal helpers

```python
def _get_today_games() -> list[dict]:
    ...

def _is_eligible_game_status(status: str) -> bool:
    ...

def _resolve_park(home_team_id: int) -> dict | None:
    ...

def _select_first_pitch_weather(hourly_weather: dict, game_datetime: str) -> dict:
    ...

def _determine_roof_status(park: dict, weather: dict) -> str:
    ...

def _calculate_game_factors(game: dict, park: dict, weather: dict) -> dict:
    ...

def _build_traits(...) -> list[str]:
    ...

def _build_summary(...) -> str:
    ...

def _build_highlights(games: list[dict]) -> dict:
    ...
```

---

## 3. Weather client

### File
`app/clients/weather_client.py`

### Responsibility
Fetch and normalize weather data from Open-Meteo.

### Suggested public function

```python
def get_forecast_for_park(lat: float, lon: float) -> dict:
    ...
```

### Behavior
- request hourly and daily weather in one call
- normalize to backend-friendly field names
- return enough data to select first-pitch hour
- use a TTL cache to avoid repeated weather requests per stadium

### Cache recommendation
- weather by park coordinates: **15 minutes TTL**

Cache key example:
- `weather:41.9484:-87.6553:2026-04-10`

---

## 4. Park metadata module

### File
`app/data/mlb_parks.py`

### Shape recommendation
Use a plain Python dictionary keyed by `home_team_id`.

Example:

```python
MLB_PARKS = {
    112: {
        "venue_name": "Wrigley Field",
        "city": "Chicago",
        "state": "IL",
        "lat": 41.9484,
        "lon": -87.6553,
        "roof_type": "open",
        "field_orientation_deg": 35,
        "wind_receptivity": 1.25,
        "park_runs_pct": -2,
        "park_hr_pct": 2,
    }
}
```

### Notes
- `wind_receptivity` should be higher for parks like Wrigley.
- baseline park values should be **modest** because v1 is weather-dominant.
- avoid overfitting the first version.

---

## Modeling Approach

## Philosophy
V1 is an **explainable rules engine**, not a trained predictive model.

The calculation should answer:
- does today's environment help or hurt scoring?
- does the wind make homers more or less likely?

### Final outputs to model
- `combined_runs_pct`
- `combined_hr_pct`

### Supporting breakdown
- `stadium_runs_pct`
- `weather_runs_pct`
- `stadium_hr_pct`
- `weather_hr_pct`

---

## Weather factor components

### A. Temperature effect
Use first-pitch temperature as the main temperature input.

Recommended baseline:
- neutral around **70°F**
- colder than 70 suppresses offense
- warmer than 70 modestly helps offense

Suggested starting formulas:

```text
temp_delta = game_temp_f - 70
weather_runs_temp_pct = clamp(temp_delta * 0.35, -12, 10)
weather_hr_temp_pct = clamp(temp_delta * 0.45, -15, 12)
```

This keeps temperature meaningful without overpowering wind.

### B. Wind effect
Wind will be the main driver in v1.

We should calculate whether the wind is:
- blowing out
- blowing in
- crosswind

#### Wind direction calculation
- park orientation is stored as the direction from home plate toward center field
- Open-Meteo wind direction is where wind comes **from**
- convert to wind travel direction:

```text
wind_to_deg = (wind_direction_degrees + 180) % 360
```

- compare `wind_to_deg` to `field_orientation_deg`
- compute alignment using cosine of the angular difference
  - close to `+1` => blowing out
  - close to `-1` => blowing in
  - near `0` => crosswind

#### Suggested wind formulas

```text
wind_scalar = alignment * wind_speed_mph * wind_receptivity
weather_runs_wind_pct = clamp(wind_scalar * 0.9, -18, 18)
weather_hr_wind_pct = clamp(wind_scalar * 1.35, -25, 25)
```

This makes HR more sensitive than runs.

### C. Precipitation effect
Precipitation will matter in v1 in two ways:

1. **roof decision** for retractable-roof parks
2. small offensive penalty in open-air parks when rain chance is meaningful

Suggested starting rule:

```text
if roof_status_assumption == "open" and precipitation_probability_pct >= 40:
    precipitation_runs_pct = -2
    precipitation_hr_pct = -2
else:
    precipitation_runs_pct = 0
    precipitation_hr_pct = 0
```

This gives precip a minor role without overcomplicating the model.

---

## Roof logic

### Fixed dome
- always treated as closed
- mute weather effects almost entirely

### Open-air park
- always treated as open
- full weather effects apply

### Retractable roof
Use assumption-based logic.

Assume **closed** if any of the following are true:
- precipitation probability `>= 35%`
- game temperature `< 58°F`
- wind speed `>= 14 mph`

Otherwise assume **open**.

### Weather dampening when roof is closed
If roof is closed:
- wind effect = 0
- precipitation effect = 0
- temperature effect reduced heavily or removed

Recommended v1 behavior:

```text
fixed_dome:
  weather effects = 0

retractable + closed:
  weather_runs_pct = round(weather_runs_pct * 0.15)
  weather_hr_pct = round(weather_hr_pct * 0.15)
```

This preserves a tiny environmental signal without pretending full outdoor conditions apply.

---

## Stadium baseline effect

Because this is weather-dominant v1, baseline park adjustments should stay modest.

Examples of approach:
- Coors: strong positive baseline
- Great American: mild HR-positive baseline
- Petco: mild negative baseline
- Wrigley: modest baseline, but very high wind receptivity
- Tropicana: neutral weather, modest static park baseline only

### Suggested range
- `park_runs_pct`: roughly `-6` to `+8`
- `park_hr_pct`: roughly `-8` to `+10`

---

## Combined formulas

### Weather-only totals

```text
weather_runs_pct = weather_runs_temp_pct + weather_runs_wind_pct + precipitation_runs_pct
weather_hr_pct = weather_hr_temp_pct + weather_hr_wind_pct + precipitation_hr_pct
```

### Final totals

```text
combined_runs_pct = stadium_runs_pct + weather_runs_pct
combined_hr_pct = stadium_hr_pct + weather_hr_pct
```

### Output normalization
- round to whole percentages
- clamp to sensible maximums

Recommended clamps:

```text
combined_runs_pct: -25 to +25
combined_hr_pct: -35 to +35
```

---

## Rating scale

Use `combined_runs_pct` to generate a card badge.

Suggested mapping:

- `>= 10` => `strong_hitter`
- `4 to 9` => `slight_hitter`
- `-3 to 3` => `neutral`
- `-9 to -4` => `slight_pitcher`
- `<= -10` => `strong_pitcher`

This rating is simple and frontend-friendly.

---

## Traits generation

Traits should be short tags that help the card explain itself.

Possible traits:
- `warm`
- `hot`
- `cold`
- `very_cold`
- `wind_out`
- `wind_in`
- `crosswind`
- `wind_sensitive_park`
- `roof_closed_assumed`
- `rain_risk`
- `hitter_friendly_park`
- `pitcher_friendly_park`

Recommended logic:
- temp <= 50 => `cold`
- temp <= 42 => `very_cold`
- temp >= 80 => `hot`
- alignment >= 0.55 => `wind_out`
- alignment <= -0.55 => `wind_in`
- otherwise => `crosswind`
- wind receptivity >= 1.15 => `wind_sensitive_park`
- precip >= 35 => `rain_risk`
- retractable + closed => `roof_closed_assumed`

---

## Summary generation

Each game should get a short summary sentence.

Examples:
- `Warm temperatures and wind blowing out make this one of the better run environments on the slate.`
- `Cold conditions with wind blowing in create a pitcher-friendly setup for scoring.`
- `With the roof likely closed, weather should have limited impact on this matchup.`

Summary should be deterministic and template-based.

Priority order for sentence generation:
1. roof closed assumption
2. strong wind signal
3. strong cold/warm signal
4. fallback neutral sentence

---

## Slate highlights

Top-level `highlights` should be compact, not editorial.

Recommended items:
- best hitter environment by `combined_runs_pct`
- most pitcher-friendly by `combined_runs_pct`
- warmest game by `game_temp_f`
- coldest game by `game_temp_f`
- windiest game by `wind_speed_mph`

This gives the frontend enough summary value without generating paragraphs.

---

## Caching Strategy

Use the existing TTL cache pattern in `cache.py`.

### Endpoint cache
- key: `park_factors:today:{reference_date}`
- TTL: **300 seconds**

### Weather cache per park
- key: `weather:{lat}:{lon}:{reference_date}`
- TTL: **900 seconds**

### Why this works
- today-only endpoint changes slowly enough for short caching
- status and scheduled slate still stay reasonably fresh
- forecast data does not need to be re-fetched on every request

---

## Error Handling Strategy

### If weather fetch fails for one game
Do **not** fail the whole endpoint.

Fallback behavior:
- return game card with:
  - weather values = `null` where needed
  - factors based on stadium baseline only
  - summary like `Weather data unavailable; card is using stadium baseline only.`

### If park metadata is missing for a team
- skip the game or return a safe fallback card
- recommended: return the card with `summary` indicating missing park metadata only if we want visibility during development
- for production, safer to skip and log

### If MLB schedule fetch fails
- return `{ "date": ..., "generated_at": ..., "highlights": {}, "games": [] }`
- log the error

---

## Testing Plan

### File
`tests/test_park_factors.py`

### Test coverage

#### Service tests
1. returns eligible scheduled and in-progress games only
2. excludes final/postponed/cancelled games
3. maps home team to park metadata
4. chooses first-pitch weather hour correctly
5. applies wind-out boost correctly
6. applies wind-in penalty correctly
7. applies cold-weather penalty correctly
8. closes retractable roof under bad weather assumptions
9. mutes weather effect when roof is assumed closed
10. returns stadium-only fallback when weather client fails
11. builds highlights correctly
12. uses cache on repeat calls

#### Route tests
1. `GET /park-factors` returns 200
2. route returns JSON payload from service

### Test style
Follow the existing `unittest` + `patch` style already used in:
- `tests/test_yesterday_results.py`

---

## Implementation Steps

### Step 1: Add park metadata
Create `app/data/mlb_parks.py` with all MLB home parks and initial baseline values.

### Step 2: Add weather client
Create `app/clients/weather_client.py` with Open-Meteo integration and response normalization.

### Step 3: Add park factor service
Create `app/services/park_factor_service.py` with:
- schedule fetch
- game filtering
- weather selection
- roof logic
- impact calculations
- traits / summary / highlights
- endpoint-level caching

### Step 4: Add API route
Create `app/api/park_factors.py` and expose `GET /park-factors`.

### Step 5: Register blueprint
Update `app/__init__.py` to register the new blueprint.

### Step 6: Add tests
Create `tests/test_park_factors.py` with mocked MLB and weather responses.

### Step 7: Validate locally
Run the endpoint against a real slate and inspect the response shape for frontend readiness.

---

## Suggested Initial Defaults for Park Metadata

These should be intentionally conservative.

Example categories:
- **High wind receptivity:** Wrigley, Oracle, Great American
- **Moderate wind receptivity:** Camden, Kauffman, Comerica
- **Low wind receptivity:** Citi, Dodger, Petco
- **Fixed dome:** Tropicana
- **Retractable roof:** Rogers Centre, American Family Field, T-Mobile, loanDepot, Chase, Globe Life, Minute Maid

Baseline values should be reviewed manually after first implementation.

---

## Future Enhancements

After v1 is live, good next steps are:

1. support `?date=YYYY-MM-DD`
2. add doubles/triples/singles impacts
3. improve park baselines using historical data
4. incorporate humidity and pressure if justified
5. infer roof status from richer game/venue signals if available
6. add live weather mode for in-progress games
7. produce richer slate summary text
8. add confidence score or data quality flag

---

## Recommended Implementation Notes

- Do **not** reuse `schedule_service.get_today_schedule()` directly if its date filtering is too tied to Eastern time assumptions.
- For this feature, the service should fetch the slate directly from `mlb_stats_client.get_schedule(...)` for the reference date and then filter statuses itself.
- Keep all formulas centralized in the service so tuning is easy.
- Keep the park metadata file simple and explicit for maintainability.
- Keep the first version explainable. We should be able to answer why a game is `+8% runs` or `-12% runs`.

---

## Final Recommendation

Build this as a **today-only, card-focused, weather-dominant park factors endpoint** with:

- Open-Meteo forecast data
- local stadium metadata
- first-pitch weather selection
- simple but explainable runs and HR scoring
- compact highlights + per-game summaries

This gives us a strong v1 that is useful for the frontend immediately and leaves room for a more statistical model later.
