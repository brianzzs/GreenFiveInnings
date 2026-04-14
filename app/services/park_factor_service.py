import asyncio
import datetime
import math
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app import season_context
from app.clients import mlb_stats_client, weather_client
from app.data.mlb_parks import get_park_by_team_or_venue
from app.services.schedule_service import COMPLETED_GAME_STATUSES
from app.utils.calculations import TEAM_NAMES
from cache import get_ttl_cache, set_ttl_cache

PARK_FACTORS_CACHE_PREFIX = "park_factors:today"
PARK_FACTORS_TTL_SECONDS = 300
TEAM_LOGO_URL_TEMPLATE = "https://www.mlbstatic.com/team-logos/{team_id}.svg"
EXCLUDED_GAME_STATUSES = COMPLETED_GAME_STATUSES | {
    "Postponed",
    "Cancelled",
    "Suspended",
}

RUNS_WEIGHT_HR = 0.50
RUNS_WEIGHT_2B3B = 0.30
RUNS_WEIGHT_1B = 0.20

CLAMP_COMBINED_RUNS = (-45, 35)
CLAMP_COMBINED_HR = (-50, 40)
CLAMP_COMBINED_2B3B = (-35, 30)
CLAMP_COMBINED_1B = (-25, 20)

CLAMP_TEMP_HR = (-18, 15)
CLAMP_TEMP_2B3B = (-10, 8)
CLAMP_TEMP_1B = (-6, 5)

CLAMP_WIND_HR = (-40, 40)
CLAMP_WIND_2B3B = (-20, 20)
CLAMP_WIND_1B = (-4, 4)

CLAMP_HUMIDITY_HR = (-3, 3)
CLAMP_HUMIDITY_2B3B = (-2, 2)

DOME_DAMPENING_RETRACTABLE = 0.08


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _round_pct(value: float) -> int:
    return int(round(value))


def _parse_game_datetime(game_datetime: str) -> Optional[datetime.datetime]:
    if not game_datetime:
        return None
    try:
        return datetime.datetime.strptime(game_datetime, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.UTC
        )
    except ValueError:
        return None


def _team_abbreviation(team_id: int, fallback_name: Optional[str]) -> str:
    team_name = TEAM_NAMES.get(team_id)
    if team_name:
        return team_name.split()[0]
    if fallback_name:
        return fallback_name.split()[0][:3].upper()
    return "TBD"


def _build_logo_url(team_id: int) -> str:
    return TEAM_LOGO_URL_TEMPLATE.format(team_id=team_id)


def _build_matchup_label(game: dict[str, Any]) -> str:
    away_abbreviation = _team_abbreviation(game["away_id"], game.get("away_name"))
    home_abbreviation = _team_abbreviation(game["home_id"], game.get("home_name"))
    return f"{away_abbreviation} @ {home_abbreviation}"


def _is_eligible_game_status(status: Optional[str]) -> bool:
    if not status:
        return False
    return status not in EXCLUDED_GAME_STATUSES


def _resolve_park(game: dict[str, Any]) -> Optional[dict[str, Any]]:
    return get_park_by_team_or_venue(game.get("home_id"), game.get("venue_name"))


def _angle_difference_degrees(first: float, second: float) -> float:
    return ((first - second + 180) % 360) - 180


def _compute_wind_alignment(
    field_orientation_deg: float, wind_from_deg: float
) -> float:
    wind_to_deg = (wind_from_deg + 180) % 360
    delta = _angle_difference_degrees(wind_to_deg, field_orientation_deg)
    return math.cos(math.radians(delta))


def _wind_direction_label(
    alignment: Optional[float], wind_speed_mph: Optional[float]
) -> Optional[str]:
    if alignment is None or wind_speed_mph is None:
        return None
    if wind_speed_mph < 3:
        return "light"
    if alignment >= 0.35:
        return "out"
    if alignment <= -0.35:
        return "in"
    return "cross"


def _select_first_pitch_weather(
    forecast: dict[str, Any],
    game_datetime: str,
) -> Optional[dict[str, Any]]:
    game_time_utc = _parse_game_datetime(game_datetime)
    if game_time_utc is None:
        return None

    timezone_name = forecast.get("timezone", "UTC")
    try:
        local_timezone = ZoneInfo(timezone_name)
    except Exception:
        local_timezone = ZoneInfo("UTC")

    game_time_local = game_time_utc.astimezone(local_timezone)
    hourly_entries = forecast.get("hourly", [])
    if not hourly_entries:
        return None

    nearest_hour = None
    nearest_delta_seconds = None
    for hourly_entry in hourly_entries:
        time_value = hourly_entry.get("time")
        if not time_value:
            continue
        hourly_time = datetime.datetime.strptime(time_value, "%Y-%m-%dT%H:%M").replace(
            tzinfo=local_timezone
        )
        delta_seconds = abs((hourly_time - game_time_local).total_seconds())
        if nearest_delta_seconds is None or delta_seconds < nearest_delta_seconds:
            nearest_hour = hourly_entry
            nearest_delta_seconds = delta_seconds

    if nearest_hour is None:
        return None

    daily_weather = forecast.get("daily", {}).get(
        game_time_local.date().isoformat(), {}
    )
    return {
        "game_temp_f": nearest_hour.get("temperature_f"),
        "temp_min_f": daily_weather.get(
            "temp_min_f", nearest_hour.get("temperature_f")
        ),
        "temp_max_f": daily_weather.get(
            "temp_max_f", nearest_hour.get("temperature_f")
        ),
        "wind_speed_mph": nearest_hour.get("wind_speed_mph"),
        "wind_gust_mph": nearest_hour.get("wind_gust_mph"),
        "wind_direction_degrees": nearest_hour.get("wind_direction_degrees"),
        "precipitation_probability_pct": nearest_hour.get(
            "precipitation_probability_pct"
        ),
        "humidity_pct": nearest_hour.get("humidity_pct"),
    }


def _determine_roof_status(
    park: dict[str, Any], weather: Optional[dict[str, Any]]
) -> str:
    roof_type = park["roof_type"]
    if roof_type == "fixed_dome":
        return "closed"
    if roof_type == "open" or not weather:
        return "open"

    precipitation_probability_pct = weather.get("precipitation_probability_pct") or 0
    game_temp_f = weather.get("game_temp_f") or 0
    wind_speed_mph = weather.get("wind_speed_mph") or 0

    if precipitation_probability_pct >= 35 or game_temp_f < 58 or wind_speed_mph >= 14:
        return "closed"
    return "open"


def _calculate_weather_effects(
    park: dict[str, Any],
    weather: Optional[dict[str, Any]],
    roof_status_assumption: str,
) -> dict[str, Any]:
    if not weather:
        return {
            "weather_runs_pct": 0,
            "weather_hr_pct": 0,
            "weather_2b3b_pct": 0,
            "weather_1b_pct": 0,
            "wind_alignment": None,
            "wind_direction_label": None,
        }

    game_temp_f = weather.get("game_temp_f")
    wind_speed_mph = weather.get("wind_speed_mph")
    wind_gust_mph = weather.get("wind_gust_mph")
    wind_direction_degrees = weather.get("wind_direction_degrees")
    precipitation_probability_pct = weather.get("precipitation_probability_pct") or 0
    humidity_pct = weather.get("humidity_pct")

    temp_delta = (game_temp_f or 70) - 70
    temp_hr_pct = _clamp(temp_delta * 0.45, *CLAMP_TEMP_HR)
    temp_2b3b_pct = _clamp(temp_delta * 0.25, *CLAMP_TEMP_2B3B)
    temp_1b_pct = _clamp(temp_delta * 0.15, *CLAMP_TEMP_1B)

    wind_alignment = None
    wind_hr_pct = 0.0
    wind_2b3b_pct = 0.0
    wind_1b_pct = 0.0
    if wind_speed_mph is not None and wind_direction_degrees is not None:
        wind_alignment = _compute_wind_alignment(
            park["field_orientation_deg"],
            wind_direction_degrees,
        )
        effective_wind = wind_speed_mph * 0.6 + (wind_gust_mph or wind_speed_mph) * 0.4
        wind_scalar = wind_alignment * effective_wind * park["wind_receptivity"]
        wind_hr_pct = _clamp(wind_scalar * 1.35, *CLAMP_WIND_HR)
        wind_2b3b_pct = _clamp(wind_scalar * 0.70, *CLAMP_WIND_2B3B)
        wind_1b_pct = _clamp(wind_scalar * 0.10, *CLAMP_WIND_1B)

    humidity_delta = (humidity_pct or 50) - 50
    humidity_hr_pct = _clamp(humidity_delta * -0.06, *CLAMP_HUMIDITY_HR)
    humidity_2b3b_pct = _clamp(humidity_delta * -0.03, *CLAMP_HUMIDITY_2B3B)

    precipitation_runs_base = 0.0
    precipitation_hr_pct = 0.0
    precipitation_2b3b_pct = 0.0
    precipitation_1b_pct = 0.0
    if roof_status_assumption == "open" and precipitation_probability_pct >= 35:
        precipitation_runs_base = _clamp(
            -(precipitation_probability_pct - 35) * 0.08, -5, 0
        )
        precipitation_hr_pct = precipitation_runs_base * 1.0
        precipitation_2b3b_pct = precipitation_runs_base * 0.5
        precipitation_1b_pct = precipitation_runs_base * 0.8

    weather_hr_pct = temp_hr_pct + wind_hr_pct + humidity_hr_pct + precipitation_hr_pct
    weather_2b3b_pct = (
        temp_2b3b_pct + wind_2b3b_pct + humidity_2b3b_pct + precipitation_2b3b_pct
    )
    weather_1b_pct = temp_1b_pct + wind_1b_pct + precipitation_1b_pct

    if park["roof_type"] == "fixed_dome":
        weather_hr_pct = 0.0
        weather_2b3b_pct = 0.0
        weather_1b_pct = 0.0
    elif roof_status_assumption == "closed":
        weather_hr_pct *= DOME_DAMPENING_RETRACTABLE
        weather_2b3b_pct *= DOME_DAMPENING_RETRACTABLE
        weather_1b_pct *= DOME_DAMPENING_RETRACTABLE

    weather_runs_pct = (
        weather_hr_pct * RUNS_WEIGHT_HR
        + weather_2b3b_pct * RUNS_WEIGHT_2B3B
        + weather_1b_pct * RUNS_WEIGHT_1B
    )

    return {
        "weather_runs_pct": _round_pct(weather_runs_pct),
        "weather_hr_pct": _round_pct(weather_hr_pct),
        "weather_2b3b_pct": _round_pct(weather_2b3b_pct),
        "weather_1b_pct": _round_pct(weather_1b_pct),
        "wind_alignment": wind_alignment,
        "wind_direction_label": _wind_direction_label(wind_alignment, wind_speed_mph),
    }


def _build_rating(combined_runs_pct: int) -> str:
    if combined_runs_pct >= 10:
        return "strong_hitter"
    if combined_runs_pct >= 4:
        return "slight_hitter"
    if combined_runs_pct <= -10:
        return "strong_pitcher"
    if combined_runs_pct <= -4:
        return "slight_pitcher"
    return "neutral"


def _compute_stadium_runs_pct(park: dict[str, Any]) -> int:
    return _round_pct(
        park["park_hr_pct"] * RUNS_WEIGHT_HR
        + park["park_2b3b_pct"] * RUNS_WEIGHT_2B3B
        + park["park_1b_pct"] * RUNS_WEIGHT_1B
    )


def _build_traits(
    park: dict[str, Any],
    weather: Optional[dict[str, Any]],
    roof_status_assumption: str,
    wind_direction_label: Optional[str],
) -> list[str]:
    traits: list[str] = []

    if park["wind_receptivity"] >= 1.15:
        traits.append("wind_sensitive_park")
    stadium_runs_pct = _compute_stadium_runs_pct(park)
    if stadium_runs_pct >= 3:
        traits.append("hitter_friendly_park")
    elif stadium_runs_pct <= -3:
        traits.append("pitcher_friendly_park")

    if roof_status_assumption == "closed" and park["roof_type"] == "retractable":
        traits.append("roof_closed_assumed")

    if not weather:
        traits.append("weather_unavailable")
        return traits

    game_temp_f = weather.get("game_temp_f")
    precipitation_probability_pct = weather.get("precipitation_probability_pct") or 0

    if game_temp_f is not None:
        if game_temp_f <= 42:
            traits.append("very_cold")
        elif game_temp_f <= 50:
            traits.append("cold")
        elif game_temp_f >= 80:
            traits.append("hot")
        elif game_temp_f >= 72:
            traits.append("warm")

    if wind_direction_label == "out":
        traits.append("wind_out")
    elif wind_direction_label == "in":
        traits.append("wind_in")
    elif wind_direction_label == "cross":
        traits.append("crosswind")

    if precipitation_probability_pct >= 35:
        traits.append("rain_risk")

    return traits


def _build_summary(
    park: dict[str, Any],
    weather: Optional[dict[str, Any]],
    roof_status_assumption: str,
    rating: str,
    wind_direction_label: Optional[str],
) -> str:
    if not weather:
        return "Weather data unavailable; card is using stadium baseline only."

    if roof_status_assumption == "closed" and park["roof_type"] == "retractable":
        return "With the roof likely closed, weather should have limited impact on this matchup."
    if park["roof_type"] == "fixed_dome":
        return "Indoor conditions should keep weather from materially affecting this matchup."

    game_temp_f = weather.get("game_temp_f")
    if wind_direction_label == "out" and rating in {"strong_hitter", "slight_hitter"}:
        return (
            "Wind blowing out boosts the run environment and gives hitters a lift here."
        )
    if wind_direction_label == "in" and rating in {"strong_pitcher", "slight_pitcher"}:
        return "Wind blowing in should suppress carry and make this a tougher scoring environment."
    if game_temp_f is not None and game_temp_f <= 50:
        return "Cold temperatures should keep offense in check unless game conditions shift."
    if game_temp_f is not None and game_temp_f >= 75:
        return "Warm temperatures make this one of the better run environments on the slate."
    return "Conditions look fairly balanced, with only a modest park and weather effect on scoring."


def _build_highlight_entry(
    game: dict[str, Any],
    value_key: str,
    value: int | float | None,
) -> dict[str, Any]:
    entry = {
        "game_id": game["game_id"],
        "label": game.get("matchup_label", "TBD @ TBD"),
        "venue": game["venue"]["name"],
    }
    if value is not None:
        entry[value_key] = value
    return entry


def _build_highlights(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {}

    best_hitter_game = max(games, key=lambda game: game["factors"]["combined_runs_pct"])
    most_pitcher_friendly_game = min(
        games, key=lambda game: game["factors"]["combined_runs_pct"]
    )

    games_with_temp = [
        game for game in games if game["weather"].get("game_temp_f") is not None
    ]
    games_with_wind = [
        game for game in games if game["weather"].get("wind_speed_mph") is not None
    ]

    highlights = {
        "best_hitter_environment": _build_highlight_entry(
            best_hitter_game,
            "runs_pct",
            best_hitter_game["factors"]["combined_runs_pct"],
        ),
        "most_pitcher_friendly": _build_highlight_entry(
            most_pitcher_friendly_game,
            "runs_pct",
            most_pitcher_friendly_game["factors"]["combined_runs_pct"],
        ),
    }

    if games_with_temp:
        warmest_game = max(
            games_with_temp, key=lambda game: game["weather"]["game_temp_f"]
        )
        coldest_game = min(
            games_with_temp, key=lambda game: game["weather"]["game_temp_f"]
        )
        highlights["warmest_game"] = _build_highlight_entry(
            warmest_game,
            "temperature_f",
            warmest_game["weather"]["game_temp_f"],
        )
        highlights["coldest_game"] = _build_highlight_entry(
            coldest_game,
            "temperature_f",
            coldest_game["weather"]["game_temp_f"],
        )

    if games_with_wind:
        windiest_game = max(
            games_with_wind, key=lambda game: game["weather"]["wind_speed_mph"]
        )
        highlights["windiest_game"] = _build_highlight_entry(
            windiest_game,
            "wind_speed_mph",
            windiest_game["weather"]["wind_speed_mph"],
        )

    return highlights


def _build_game_response(
    game: dict[str, Any],
    park: dict[str, Any],
    weather: Optional[dict[str, Any]],
    roof_status_assumption: str,
    weather_effects: dict[str, Any],
) -> dict[str, Any]:
    stadium_hr_pct = int(park["park_hr_pct"])
    stadium_2b3b_pct = int(park["park_2b3b_pct"])
    stadium_1b_pct = int(park["park_1b_pct"])
    stadium_runs_pct = _compute_stadium_runs_pct(park)

    combined_hr_pct = _round_pct(
        _clamp(stadium_hr_pct + weather_effects["weather_hr_pct"], *CLAMP_COMBINED_HR)
    )
    combined_2b3b_pct = _round_pct(
        _clamp(
            stadium_2b3b_pct + weather_effects["weather_2b3b_pct"], *CLAMP_COMBINED_2B3B
        )
    )
    combined_1b_pct = _round_pct(
        _clamp(stadium_1b_pct + weather_effects["weather_1b_pct"], *CLAMP_COMBINED_1B)
    )
    combined_runs_pct = _round_pct(
        _clamp(
            stadium_runs_pct + weather_effects["weather_runs_pct"], *CLAMP_COMBINED_RUNS
        )
    )

    rating = _build_rating(combined_runs_pct)
    traits = _build_traits(
        park,
        weather,
        roof_status_assumption,
        weather_effects.get("wind_direction_label"),
    )

    safe_weather = weather or {
        "game_temp_f": None,
        "temp_min_f": None,
        "temp_max_f": None,
        "wind_speed_mph": None,
        "wind_gust_mph": None,
        "wind_direction_degrees": None,
        "precipitation_probability_pct": None,
        "humidity_pct": None,
    }

    return {
        "game_id": game["game_id"],
        "status": game.get("status"),
        "game_datetime": game.get("game_datetime"),
        "matchup_label": _build_matchup_label(game),
        "matchup": {
            "away_team_id": game["away_id"],
            "away_team_name": game.get("away_name"),
            "away_team_logo_url": _build_logo_url(game["away_id"]),
            "home_team_id": game["home_id"],
            "home_team_name": game.get("home_name"),
            "home_team_logo_url": _build_logo_url(game["home_id"]),
        },
        "venue": {
            "name": game.get("venue_name") or park["venue_names"][0],
            "city": park["city"],
            "state": park["state"],
            "roof_type": park["roof_type"],
            "roof_status_assumption": roof_status_assumption,
        },
        "weather": {
            **safe_weather,
            "wind_direction_label": weather_effects.get("wind_direction_label"),
        },
        "factors": {
            "stadium_runs_pct": stadium_runs_pct,
            "weather_runs_pct": weather_effects["weather_runs_pct"],
            "combined_runs_pct": combined_runs_pct,
            "stadium_hr_pct": stadium_hr_pct,
            "weather_hr_pct": weather_effects["weather_hr_pct"],
            "combined_hr_pct": combined_hr_pct,
            "stadium_2b3b_pct": stadium_2b3b_pct,
            "weather_2b3b_pct": weather_effects["weather_2b3b_pct"],
            "combined_2b3b_pct": combined_2b3b_pct,
            "stadium_1b_pct": stadium_1b_pct,
            "weather_1b_pct": weather_effects["weather_1b_pct"],
            "combined_1b_pct": combined_1b_pct,
            "rating": rating,
        },
        "traits": traits,
        "summary": _build_summary(
            park,
            weather,
            roof_status_assumption,
            rating,
            weather_effects.get("wind_direction_label"),
        ),
    }


async def _fetch_weather_for_game(
    game: dict[str, Any],
    park: dict[str, Any],
    today_date: datetime.date,
) -> tuple[dict[str, Any], Optional[dict[str, Any]], str]:
    game_id = game.get("game_id")
    weather = None
    roof_status_assumption = "open" if park["roof_type"] != "fixed_dome" else "closed"
    try:
        forecast = await weather_client.get_forecast_for_park(
            park["lat"],
            park["lon"],
            today_date,
        )
        weather = _select_first_pitch_weather(forecast, game.get("game_datetime"))
        roof_status_assumption = _determine_roof_status(park, weather)
    except Exception as error:
        print(
            f"[get_today_park_factors] Error fetching weather for game {game_id}: {error}"
        )
    return game, weather, roof_status_assumption


async def get_today_park_factors() -> dict[str, Any]:
    today_date = season_context.reference_date()
    cache_key = f"{PARK_FACTORS_CACHE_PREFIX}:{today_date.isoformat()}"
    cached_payload = get_ttl_cache(cache_key)
    if cached_payload is not None:
        return cached_payload

    response_payload = {
        "date": today_date.isoformat(),
        "generated_at": datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "highlights": {},
        "games": [],
    }

    try:
        raw_games = await mlb_stats_client.get_schedule_async(
            start_date=today_date.isoformat(),
            end_date=today_date.isoformat(),
        )
    except Exception as error:
        print(f"[get_today_park_factors] Error fetching schedule: {error}")
        return set_ttl_cache(cache_key, response_payload, PARK_FACTORS_TTL_SECONDS)

    if not raw_games:
        return set_ttl_cache(cache_key, response_payload, PARK_FACTORS_TTL_SECONDS)

    eligible_games: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for game in raw_games:
        status = game.get("status")
        if not _is_eligible_game_status(status):
            continue

        game_id = game.get("game_id")
        home_id = game.get("home_id")
        away_id = game.get("away_id")
        if not game_id or not home_id or not away_id:
            continue

        park = _resolve_park(game)
        if park is None:
            print(f"[get_today_park_factors] Missing park metadata for game {game_id}")
            continue

        eligible_games.append((game, park))

    weather_tasks = [
        _fetch_weather_for_game(game, park, today_date) for game, park in eligible_games
    ]
    weather_results = await asyncio.gather(*weather_tasks, return_exceptions=True)

    processed_games: list[dict[str, Any]] = []
    for idx, result in enumerate(weather_results):
        game, park = eligible_games[idx]
        if isinstance(result, Exception):
            weather = None
            roof_status_assumption = (
                "open" if park["roof_type"] != "fixed_dome" else "closed"
            )
        else:
            _, weather, roof_status_assumption = result

        weather_effects = _calculate_weather_effects(
            park,
            weather,
            roof_status_assumption,
        )
        processed_games.append(
            _build_game_response(
                game,
                park,
                weather,
                roof_status_assumption,
                weather_effects,
            )
        )

    processed_games.sort(key=lambda game: game.get("game_datetime") or "")
    response_payload["games"] = processed_games
    response_payload["highlights"] = _build_highlights(processed_games)
    return set_ttl_cache(cache_key, response_payload, PARK_FACTORS_TTL_SECONDS)
