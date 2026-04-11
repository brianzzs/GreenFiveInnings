# Front-End Integration Guide: Park Factors

This guide explains how the front-end should integrate with the **Park Factors** backend feature.

The goal of this endpoint is to power a **today-only MLB card list** showing how weather + park conditions may affect:

- **Runs** (composite of all hit types)
- **Home runs** (HR)
- **Doubles / Triples** (2B/3B)
- **Singles** (1B)

Each hit type has its own sensitivity to temperature, wind, humidity, and precipitation. The `combined_runs_pct` is a weighted composite derived from the hit-type breakdowns.

It also provides compact slate-level highlights for quick UI summaries.

---

## Feature Summary

The backend exposes a new endpoint:

- `GET /park-factors`

It returns:
- today's MLB games
- only games that are still relevant for users:
  - scheduled
  - pregame-style statuses
  - in progress
- excludes final/postponed/cancelled games
- weather context for each game (including humidity)
- per-hit-type impact percentages (HR, 2B/3B, 1B) plus a weighted Runs composite
- simple rating badge values
- short summary text
- top-level highlights for the slate

---

## Endpoint

## `GET /park-factors`

### Purpose
Fetch today's MLB park/weather factor cards.

### Request

```http
GET /park-factors
```

### Headers
Use the same auth strategy your app already uses for the rest of the backend.

If the environment requires API auth, send one of:

```http
X-API-Key: your_api_key
```

or

```http
Authorization: Bearer your_api_key
```

### Query Params
None in v1.

This endpoint is **today only**.

---

## Response Shape

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
      "runs_pct": -39
    },
    "warmest_game": {
      "game_id": 1,
      "label": "LAA @ CIN",
      "venue": "Great American Ball Park",
      "temperature_f": 74
    },
    "coldest_game": {
      "game_id": 2,
      "label": "PIT @ CHC",
      "venue": "Wrigley Field",
      "temperature_f": 47
    },
    "windiest_game": {
      "game_id": 3,
      "label": "SF @ BAL",
      "venue": "Oriole Park at Camden Yards",
      "wind_speed_mph": 14
    }
  },
  "games": [
    {
      "game_id": 123,
      "status": "Scheduled",
      "game_datetime": "2026-04-10T18:20:00Z",
      "matchup_label": "PIT @ CHC",
      "matchup": {
        "away_team_id": 134,
        "away_team_name": "Pittsburgh Pirates",
        "away_team_logo_url": "https://www.mlbstatic.com/team-logos/134.svg",
        "home_team_id": 112,
        "home_team_name": "Chicago Cubs",
        "home_team_logo_url": "https://www.mlbstatic.com/team-logos/112.svg"
      },
      "venue": {
        "name": "Wrigley Field",
        "city": "Chicago",
        "state": "IL",
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
        "precipitation_probability_pct": 10,
        "humidity_pct": 42,
        "wind_direction_label": "in"
      },
      "factors": {
        "stadium_runs_pct": 1,
        "weather_runs_pct": -20,
        "combined_runs_pct": -19,
        "stadium_hr_pct": 1,
        "weather_hr_pct": -22,
        "combined_hr_pct": -21,
        "stadium_2b3b_pct": 0,
        "weather_2b3b_pct": -12,
        "combined_2b3b_pct": -12,
        "stadium_1b_pct": 0,
        "weather_1b_pct": -5,
        "combined_1b_pct": -5,
        "rating": "strong_pitcher"
      },
      "traits": ["wind_sensitive_park", "cold", "wind_in"],
      "summary": "Wind blowing in should suppress carry and make this a tougher scoring environment."
    }
  ]
}
```

---

## Top-Level Fields

### `date`
The effective date used by the backend.

Type:
```ts
string
```

Format:
```ts
YYYY-MM-DD
```

---

### `generated_at`
UTC timestamp showing when the payload was generated.

Type:
```ts
string
```

Format:
```ts
ISO datetime
```

---

### `highlights`
Small summary object for the slate.

Use this for:
- header chips
- hero callouts
- quick "best/worst environment" labels

Possible keys:
- `best_hitter_environment`
- `most_pitcher_friendly`
- `warmest_game`
- `coldest_game`
- `windiest_game`

Each highlight object includes:
- `game_id`
- `label`
- `venue`
- one metric field

Example:

```json
{
  "game_id": 1,
  "label": "LAA @ CIN",
  "venue": "Great American Ball Park",
  "runs_pct": 9
}
```

If no valid games are available, `highlights` may be:

```json
{}
```

---

### `games`
Array of game cards for the frontend.

Type:
```ts
ParkFactorGame[]
```

The frontend should render these as the main content list.

---

## Game Object Reference

## `game_id`
Unique MLB game identifier.

```ts
number
```

---

## `status`
Backend passes through the MLB game status string.

Examples:
- `Scheduled`
- `Pre-Game`
- `Warmup`
- `In Progress`
- `Delayed Start`
- `Delayed`

Recommended front-end usage:
- show a status pill
- use a stronger visual style for `In Progress`

---

## `game_datetime`
Official game start datetime in UTC.

```ts
string
```

Frontend should convert this to the user's preferred timezone.

---

## `matchup_label`
Compact string for cards.

Examples:
- `PIT @ CHC`
- `LAA @ CIN`

Use this when you need a simple card title.

---

## `matchup`
Team block.

```json
{
  "away_team_id": 134,
  "away_team_name": "Pittsburgh Pirates",
  "away_team_logo_url": "https://www.mlbstatic.com/team-logos/134.svg",
  "home_team_id": 112,
  "home_team_name": "Chicago Cubs",
  "home_team_logo_url": "https://www.mlbstatic.com/team-logos/112.svg"
}
```

Recommended UI usage:
- show both logos
- show away team first
- show full names or abbreviations depending on card size

---

## `venue`
Venue metadata.

```json
{
  "name": "Wrigley Field",
  "city": "Chicago",
  "state": "IL",
  "roof_type": "open",
  "roof_status_assumption": "open"
}
```

### `roof_type`
Possible values:
- `open`
- `retractable`
- `fixed_dome`

### `roof_status_assumption`
Possible values:
- `open`
- `closed`

Notes:
- `roof_status_assumption` matters most for retractable-roof parks
- if `closed`, weather impact is intentionally muted by the model (8% dampening)

Recommended UI usage:
- show a small roof badge only if useful
- or surface it only in expanded card detail

---

## `weather`
Weather snapshot selected for **first pitch**.

```json
{
  "game_temp_f": 47,
  "temp_min_f": 43,
  "temp_max_f": 50,
  "wind_speed_mph": 9,
  "wind_gust_mph": 14,
  "wind_direction_degrees": 25,
  "precipitation_probability_pct": 10,
  "humidity_pct": 42,
  "wind_direction_label": "in"
}
```

### Field meanings

#### `game_temp_f`
Temperature near first pitch.

#### `temp_min_f`
Daily minimum temperature for that park/day.

#### `temp_max_f`
Daily maximum temperature for that park/day.

#### `wind_speed_mph`
Wind speed near first pitch.

#### `wind_gust_mph`
Wind gust speed near first pitch. The model uses a blended effective wind (`speed*0.6 + gust*0.4`) to calculate wind impact, since gusts significantly affect ball flight.

#### `wind_direction_degrees`
Raw wind direction in degrees.

Most front-end use cases should prefer `wind_direction_label` over plotting this directly.

#### `precipitation_probability_pct`
Chance of precipitation around first pitch.

#### `humidity_pct`
Relative humidity percentage near first pitch.

High humidity means denser air, which suppresses home run carry. Low humidity (dry air) slightly aids ball flight. The model uses 50% as a neutral baseline.

Recommended UI usage:
- show in expanded card detail
- a value above 70% or below 30% is worth surfacing to the user

#### `wind_direction_label`
Normalized label for easier UI.

Possible values:
- `out`
- `in`
- `cross`
- `light`
- `null`

Recommended display:
- `out` → "Wind Out"
- `in` → "Wind In"
- `cross` → "Crosswind"
- `light` → "Light Wind"

### Nullability
Some weather fields may be `null` if weather data is unavailable.

Example fallback:

```json
{
  "game_temp_f": null,
  "temp_min_f": null,
  "temp_max_f": null,
  "wind_speed_mph": null,
  "wind_gust_mph": null,
  "wind_direction_degrees": null,
  "precipitation_probability_pct": null,
  "humidity_pct": null,
  "wind_direction_label": null
}
```

The front-end must handle this gracefully.

---

## `factors`
Model outputs for the card. Each hit type is modeled independently with different weather sensitivities:

| Factor | Most sensitive to | Least sensitive to |
|---|---|---|
| **HR** | Wind, Temperature, Humidity | Precipitation |
| **2B/3B** | Wind, Temperature, Humidity | Precipitation |
| **1B** | Precipitation, Cold | Wind |

The `combined_runs_pct` is a **weighted composite**:
```
runs = hr * 0.50 + 2b3b * 0.30 + 1b * 0.20
```

```json
{
  "stadium_runs_pct": 1,
  "weather_runs_pct": -20,
  "combined_runs_pct": -19,
  "stadium_hr_pct": 1,
  "weather_hr_pct": -22,
  "combined_hr_pct": -21,
  "stadium_2b3b_pct": 0,
  "weather_2b3b_pct": -12,
  "combined_2b3b_pct": -12,
  "stadium_1b_pct": 0,
  "weather_1b_pct": -5,
  "combined_1b_pct": -5,
  "rating": "strong_pitcher"
}
```

### Primary fields for UI

#### `combined_runs_pct`
Main scoring signal for the matchup. Weighted composite of all hit types.

Interpretation examples:
- positive → better run-scoring environment
- negative → tougher run-scoring environment

Possible range: approximately **-45 to +35**.

Suggested display examples:
- `+9% Runs`
- `-39% Runs`

#### `combined_hr_pct`
Home run environment signal. Most sensitive to wind and temperature.

Possible range: approximately **-50 to +40**.

Suggested display examples:
- `+6% HR`
- `-46% HR`

#### `combined_2b3b_pct`
Doubles and triples environment signal. Moderately sensitive to wind and temperature.

Possible range: approximately **-35 to +30**.

Suggested display examples:
- `+8% 2B/3B`
- `-27% 2B/3B`

#### `combined_1b_pct`
Singles environment signal. Most affected by cold (bat speed) and rain (visibility), least affected by wind.

Possible range: approximately **-25 to +20**.

Suggested display examples:
- `+7% 1B`
- `-10% 1B`

### Breakdown fields

Each hit type has three layers:

#### Stadium baselines
- `stadium_runs_pct` — derived weighted composite of stadium hit-type baselines
- `stadium_hr_pct` — static park-only HR adjustment
- `stadium_2b3b_pct` — static park-only doubles/triples adjustment
- `stadium_1b_pct` — static park-only singles adjustment

#### Weather-only adjustments
- `weather_runs_pct` — weighted composite of weather hit-type effects
- `weather_hr_pct` — weather-only HR adjustment
- `weather_2b3b_pct` — weather-only doubles/triples adjustment
- `weather_1b_pct` — weather-only singles adjustment

#### Combined totals
- `combined_*` = stadium + weather, clamped to sensible maximums

These breakdowns can be shown in expanded details or tooltips to explain why a game rates the way it does.

### `rating`
Badge-friendly classification based on `combined_runs_pct`.

Possible values:
- `strong_hitter`
- `slight_hitter`
- `neutral`
- `slight_pitcher`
- `strong_pitcher`

Threshold mapping:
- `>= +10` → `strong_hitter`
- `+4 to +9` → `slight_hitter`
- `-3 to +3` → `neutral`
- `-9 to -4` → `slight_pitcher`
- `<= -10` → `strong_pitcher`

Recommended front-end mapping:

```ts
const ratingLabelMap = {
  strong_hitter: 'Strong Hitter',
  slight_hitter: 'Slight Hitter',
  neutral: 'Neutral',
  slight_pitcher: 'Slight Pitcher',
  strong_pitcher: 'Strong Pitcher'
}
```

Recommended color mapping:
- `strong_hitter` → green
- `slight_hitter` → light green
- `neutral` → gray
- `slight_pitcher` → light red / orange
- `strong_pitcher` → red

---

## `traits`
Short tags that help explain the environment.

Examples:
- `wind_sensitive_park`
- `hitter_friendly_park`
- `pitcher_friendly_park`
- `roof_closed_assumed`
- `weather_unavailable`
- `very_cold`
- `cold`
- `warm`
- `hot`
- `wind_out`
- `wind_in`
- `crosswind`
- `rain_risk`

Recommended UI usage:
- show 2 to 4 tags max on the card
- use the full set in expanded mode if desired

Suggested display mapping:

```ts
const traitLabelMap = {
  wind_sensitive_park: 'Wind Sensitive',
  hitter_friendly_park: 'Hitter Park',
  pitcher_friendly_park: 'Pitcher Park',
  roof_closed_assumed: 'Roof Likely Closed',
  weather_unavailable: 'Weather Unavailable',
  very_cold: 'Very Cold',
  cold: 'Cold',
  warm: 'Warm',
  hot: 'Hot',
  wind_out: 'Wind Out',
  wind_in: 'Wind In',
  crosswind: 'Crosswind',
  rain_risk: 'Rain Risk'
}
```

---

## `summary`
Short human-readable explanation for the card.

Examples:
- `Wind blowing out boosts the run environment and gives hitters a lift here.`
- `Wind blowing in should suppress carry and make this a tougher scoring environment.`
- `Cold temperatures should keep offense in check unless game conditions shift.`
- `Warm temperatures make this one of the better run environments on the slate.`
- `With the roof likely closed, weather should have limited impact on this matchup.`
- `Indoor conditions should keep weather from materially affecting this matchup.`
- `Weather data unavailable; card is using stadium baseline only.`

Recommended UI usage:
- show on expanded card
- or show as secondary body text below the key numbers

---

## Model Details

### How the model works

The model is a **rules-based, explainable engine** — not a trained ML model. Each weather factor is calculated independently per hit type, then combined.

#### Temperature effect
Baseline: 70°F is neutral.

| Hit type | Coefficient per °F from 70 | Clamp |
|---|---|---|
| HR | 0.45 | -18 to +15 |
| 2B/3B | 0.25 | -10 to +8 |
| 1B | 0.15 | -6 to +5 |

#### Wind effect
Uses a blended effective wind (`speed * 0.6 + gust * 0.4`) projected onto the field axis via cosine alignment, scaled by park wind receptivity.

| Hit type | Coefficient (wind_scalar multiplier) | Clamp |
|---|---|---|
| HR | 1.35 | -40 to +40 |
| 2B/3B | 0.70 | -20 to +20 |
| 1B | 0.10 | -4 to +4 |

#### Humidity effect
Baseline: 50% is neutral. High humidity = denser air = less carry.

| Hit type | Coefficient per % from 50 | Clamp |
|---|---|---|
| HR | -0.06 | -3 to +3 |
| 2B/3B | -0.03 | -2 to +2 |
| 1B | not affected | — |

#### Precipitation effect
Scaled penalty when precipitation probability >= 35%, only for open-air parks.

```text
base_penalty = -(precip - 35) * 0.08  clamped to -5..0
HR penalty = base_penalty * 1.0
2B/3B penalty = base_penalty * 0.5
1B penalty = base_penalty * 0.8
```

#### Roof dampening
- `fixed_dome`: all weather effects = 0
- `retractable` + `closed`: weather effects * 0.08 (heavily dampened)

#### Runs composite
```text
weather_runs = (weather_hr * 0.50) + (weather_2b3b * 0.30) + (weather_1b * 0.20)
stadium_runs = (stadium_hr * 0.50) + (stadium_2b3b * 0.30) + (stadium_1b * 0.20)
combined_runs = stadium_runs + weather_runs  (clamped -45 to +35)
```

This weighting reflects that home runs produce the most runs per event, followed by extra-base hits, then singles.

---

## TypeScript Types

Suggested front-end types:

```ts
export type ParkFactorRating =
  | 'strong_hitter'
  | 'slight_hitter'
  | 'neutral'
  | 'slight_pitcher'
  | 'strong_pitcher'

export type WindDirectionLabel = 'out' | 'in' | 'cross' | 'light' | null

export type RoofType = 'open' | 'retractable' | 'fixed_dome'
export type RoofStatusAssumption = 'open' | 'closed'

export type ParkFactorHighlight = {
  game_id: number
  label: string
  venue: string
  runs_pct?: number
  temperature_f?: number
  wind_speed_mph?: number
}

export type ParkFactorGame = {
  game_id: number
  status: string
  game_datetime: string
  matchup_label: string
  matchup: {
    away_team_id: number
    away_team_name: string
    away_team_logo_url: string
    home_team_id: number
    home_team_name: string
    home_team_logo_url: string
  }
  venue: {
    name: string
    city: string
    state: string
    roof_type: RoofType
    roof_status_assumption: RoofStatusAssumption
  }
  weather: {
    game_temp_f: number | null
    temp_min_f: number | null
    temp_max_f: number | null
    wind_speed_mph: number | null
    wind_gust_mph: number | null
    wind_direction_degrees: number | null
    precipitation_probability_pct: number | null
    humidity_pct: number | null
    wind_direction_label: WindDirectionLabel
  }
  factors: {
    stadium_runs_pct: number
    weather_runs_pct: number
    combined_runs_pct: number
    stadium_hr_pct: number
    weather_hr_pct: number
    combined_hr_pct: number
    stadium_2b3b_pct: number
    weather_2b3b_pct: number
    combined_2b3b_pct: number
    stadium_1b_pct: number
    weather_1b_pct: number
    combined_1b_pct: number
    rating: ParkFactorRating
  }
  traits: string[]
  summary: string
}

export type ParkFactorsResponse = {
  date: string
  generated_at: string
  highlights: {
    best_hitter_environment?: ParkFactorHighlight
    most_pitcher_friendly?: ParkFactorHighlight
    warmest_game?: ParkFactorHighlight
    coldest_game?: ParkFactorHighlight
    windiest_game?: ParkFactorHighlight
  }
  games: ParkFactorGame[]
}
```

---

## Example Fetch

### Fetch API

```ts
const response = await fetch(`${API_BASE_URL}/park-factors`, {
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  }
})

if (!response.ok) {
  throw new Error(`Failed to fetch park factors: ${response.status}`)
}

const data: ParkFactorsResponse = await response.json()
```

### Axios

```ts
const { data } = await axios.get<ParkFactorsResponse>(`${API_BASE_URL}/park-factors`, {
  headers: {
    'X-API-Key': API_KEY
  }
})
```

---

## Recommended UI Structure

### 1. Page/Header
Use `highlights` to render a top summary area.

Suggested chips:
- Best Hitter Spot
- Most Pitcher Friendly
- Warmest Game
- Windiest Game

### 2. Main Content
Render `games` as a card list.

Each card should ideally show:
- matchup label + logos
- venue name
- game time / status
- `combined_runs_pct` as the primary number
- `combined_hr_pct` as the secondary number
- `combined_2b3b_pct` as a tertiary detail
- `combined_1b_pct` as a tertiary detail
- rating badge
- wind + temp + humidity summary
- 2–4 traits
- short summary text

### 3. Expanded Details
Optional details section:
- full hit-type breakdown table (stadium vs weather for HR / 2B-3B / 1B / Runs)
- roof assumption
- wind gust speed
- raw wind direction degrees
- precipitation probability
- humidity percentage

---

## Suggested Card Display Logic

### Primary number
Use `combined_runs_pct` as the main large stat.

Examples:
- `+8% Runs`
- `-39% Runs`

### Secondary numbers
Use `combined_hr_pct` as the secondary stat. Optionally show `combined_2b3b_pct` and `combined_1b_pct` in an expanded view.

Suggested display:
```
HR: -21%  |  2B/3B: -12%  |  1B: -5%
```

### Weather line
Suggested display:

```ts
`${game.weather.game_temp_f ?? '--'}° | ${game.weather.wind_speed_mph ?? '--'} mph ${windLabel}`
```

Example rendered:
- `47° | 9 mph In`
- `74° | 12 mph Out`

### Humidity line
Only show in expanded details, or when humidity is notable (< 30% or > 70%).

Suggested display:
- `Humidity: 42%`

### Temp range line
Suggested display:
- `Low 43° / High 50°`

### Rain line
Only show if value is meaningful, for example `>= 20%`.

Suggested display:
- `Rain 35%`

---

## Hit-Type Breakdown Table (Expanded Card)

For the expanded card view, a small table showing the per-hit-type breakdown is recommended:

```ts
const breakdownRows = [
  { label: 'HR', stadium: game.factors.stadium_hr_pct, weather: game.factors.weather_hr_pct, combined: game.factors.combined_hr_pct },
  { label: '2B/3B', stadium: game.factors.stadium_2b3b_pct, weather: game.factors.weather_2b3b_pct, combined: game.factors.combined_2b3b_pct },
  { label: '1B', stadium: game.factors.stadium_1b_pct, weather: game.factors.weather_1b_pct, combined: game.factors.combined_1b_pct },
  { label: 'Runs', stadium: game.factors.stadium_runs_pct, weather: game.factors.weather_runs_pct, combined: game.factors.combined_runs_pct },
]
```

Example rendered:

| | Stadium | Weather | Combined |
|---|---|---|---|
| HR | +1 | -22 | -21 |
| 2B/3B | 0 | -12 | -12 |
| 1B | 0 | -5 | -5 |
| **Runs** | **+1** | **-20** | **-19** |

Format each cell as `+N%` or `-N%`, color-coded (green for positive, red for negative).

---

## Empty State Handling

If the endpoint returns:

```json
{
  "date": "2026-04-10",
  "generated_at": "2026-04-10T18:05:00Z",
  "highlights": {},
  "games": []
}
```

Recommended UI message:
- `No active park factor games are available right now.`

Possible reasons:
- no games today
- all games are final/postponed/cancelled
- backend temporarily unavailable upstream

---

## Error Handling

### HTTP errors
If request fails:
- show a non-blocking error state
- allow retry

Recommended message:
- `Unable to load park factors right now.`

### Partial weather fallback
A game may still be returned even if weather data fails.

In that case:
- weather fields may be `null` (including `humidity_pct`)
- all weather breakdown fields (`weather_hr_pct`, `weather_2b3b_pct`, `weather_1b_pct`, `weather_runs_pct`) will be `0`
- `combined_*` values will reflect stadium baseline only
- summary may read:
  - `Weather data unavailable; card is using stadium baseline only.`

The front-end should still render the card.

---

## Sorting Recommendations

Default sort recommendation:
1. by `game_datetime` ascending

Optional alternate tabs:
- best hitting environments first (sort by `combined_runs_pct` descending)
- most pitcher-friendly first (sort by `combined_runs_pct` ascending)
- warmest first

The backend already returns games sorted by `game_datetime`.

---

## Refresh Recommendations

Because this is a today-only endpoint and weather/status can shift:

Recommended client refresh strategy:
- refresh on page load
- optional auto-refresh every **5–10 minutes**

Do not refresh too aggressively. The backend caches the full response for 5 minutes and weather data for 15 minutes.

---

## Notes for Front-End Agent

### Important assumptions
- weather is selected from **first pitch**, not live current conditions
- this is designed for **pre-betting analysis**, not live betting
- in-progress games are still included
- percentages are relative environment indicators, not betting lines
- `combined_runs_pct` is the best single value for the main score-impact UI
- HR has the widest range and is most sensitive to weather
- 1B has the narrowest range and is least affected by wind
- `stadium_runs_pct` is derived from hit-type baselines, not a standalone value
- wind gusts are factored into the model via a 60/40 blend with sustained speed
- humidity above 50% suppresses HR carry; below 50% slightly aids it

### Best fields to prioritize visually
If the UI needs to stay compact, prioritize:
1. `matchup_label`
2. `status`
3. `combined_runs_pct`
4. `combined_hr_pct`
5. `rating`
6. `game_temp_f`
7. `wind_speed_mph`
8. `wind_direction_label`
9. `summary`

If the UI has room for expanded details, add:
10. `combined_2b3b_pct`
11. `combined_1b_pct`
12. `humidity_pct`
13. `wind_gust_mph`
14. stadium vs weather breakdown

---

## Minimal Card Example

A compact card could render:

- `PIT @ CHC`
- `Wrigley Field`
- `2:20 PM ET`
- badge: `Strong Pitcher`
- `Runs: -19%`
- `HR: -21%`
- `47° | 9 mph In`
- tags: `Cold`, `Wind In`, `Wind Sensitive`
- summary text

---

## Expanded Card Example

An expanded card could render:

- matchup + logos
- venue + city
- status + local time
- rating badge

**Impact table:**

| | Stadium | Weather | Total |
|---|---|---|---|
| HR | +1 | -22 | -21 |
| 2B/3B | 0 | -12 | -12 |
| 1B | 0 | -5 | -5 |
| Runs | +1 | -20 | -19 |

- temp / low / high
- wind speed / gust / direction label
- humidity
- precipitation probability
- roof type / roof assumption
- traits
- summary

---

## Final Integration Checklist

- call `GET /park-factors`
- pass API auth header if required
- type the response using the models above
- render `highlights`
- render `games` as cards
- show `combined_runs_pct` as the primary stat
- show `combined_hr_pct` as the secondary stat
- show hit-type breakdown (HR / 2B-3B / 1B) in expanded card
- handle `humidity_pct` in weather display
- support null weather values
- support empty state
- support error state
- use `rating` for badge styling
- use `combined_runs_pct` as the primary scoring indicator

---

## Backend Contact Contract Summary

### Required endpoint
- `GET /park-factors`

### Required sections in response
- `date`
- `generated_at`
- `highlights`
- `games`

### Required card fields
- `game_id`
- `status`
- `game_datetime`
- `matchup_label`
- `matchup`
- `venue`
- `weather` (includes `humidity_pct`)
- `factors` (includes HR, 2B/3B, 1B, Runs breakdowns)
- `traits`
- `summary`

This is the full contract the front-end agent should implement against.
