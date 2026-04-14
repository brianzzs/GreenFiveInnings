import asyncio
from typing import Dict, Any, List, Callable, Awaitable
from app.services import game_service, player_service, schedule_service
from app.clients import mlb_stats_client
from app.utils.calculations import TEAM_NAMES
from app.utils import helpers


async def _fetch_game_context(game_id: int) -> Dict[str, Any]:
    raw_game_data = await mlb_stats_client.get_game_data_async(game_id)
    game_data = raw_game_data.get("gameData", {})
    live_data = raw_game_data.get("liveData", {})
    boxscore_data = live_data.get("boxscore", {})
    teams_info = game_data.get("teams", {})
    away_team_info = teams_info.get("away", {})
    home_team_info = teams_info.get("home", {})
    away_team_id = away_team_info.get("id")
    home_team_id = home_team_info.get("id")

    if not away_team_id or not home_team_id:
        raise ValueError(f"Missing team ID for game {game_id}")

    away_record_data = away_team_info.get("leagueRecord", {})
    home_record_data = home_team_info.get("leagueRecord", {})
    away_record_str = (
        f"{away_record_data.get('wins', 0)}-{away_record_data.get('losses', 0)}"
    )
    home_record_str = (
        f"{home_record_data.get('wins', 0)}-{home_record_data.get('losses', 0)}"
    )
    datetime_info = game_data.get("datetime", {})
    venue_info = game_data.get("venue", {})
    status_info = game_data.get("status", {})

    pitcher_details = await player_service.fetch_and_cache_pitcher_info(
        game_id, raw_game_data
    )
    away_pitcher_id = pitcher_details.get("awayPitcherID")
    home_pitcher_id = pitcher_details.get("homePitcherID")

    away_lineup = helpers.extract_lineup(boxscore_data, "away")
    home_lineup = helpers.extract_lineup(boxscore_data, "home")

    away_lineup_status = "Confirmed"
    home_lineup_status = "Confirmed"

    if away_lineup is None:
        away_lineup = await schedule_service.get_last_game_lineup(away_team_id)
        if away_lineup is not None:
            away_lineup_status = "Expected"
        else:
            away_lineup = []
            away_lineup_status = "Unavailable"

    if home_lineup is None:
        home_lineup = await schedule_service.get_last_game_lineup(home_team_id)
        if home_lineup is not None:
            home_lineup_status = "Expected"
        else:
            home_lineup = []
            home_lineup_status = "Unavailable"

    away_pitcher_era = pitcher_details.get("awayPitcherERA", "N/A")
    home_pitcher_era = pitcher_details.get("homePitcherERA", "N/A")

    return {
        "game_id": game_id,
        "away_team_id": away_team_id,
        "home_team_id": home_team_id,
        "away_record_str": away_record_str,
        "home_record_str": home_record_str,
        "datetime_info": datetime_info,
        "venue_info": venue_info,
        "status_info": status_info,
        "pitcher_details": pitcher_details,
        "away_pitcher_id": away_pitcher_id,
        "home_pitcher_id": home_pitcher_id,
        "away_pitcher_era": away_pitcher_era,
        "home_pitcher_era": home_pitcher_era,
        "away_lineup": away_lineup,
        "home_lineup": home_lineup,
        "away_lineup_status": away_lineup_status,
        "home_lineup_status": home_lineup_status,
        "away_team_info": away_team_info,
        "home_team_info": home_team_info,
    }


def _build_h2h_tasks(
    away_lineup: List[Dict],
    home_lineup: List[Dict],
    away_pitcher_id,
    home_pitcher_id,
) -> tuple:
    tasks_to_run = []
    away_lineup_h2h_task_indices = {}
    home_lineup_h2h_task_indices = {}

    if home_pitcher_id and home_pitcher_id != "TBD":
        for player in away_lineup:
            player_id = player.get("id")
            if player_id:
                tasks_to_run.append(
                    mlb_stats_client.get_player_h2h_stats(
                        player_id,
                        home_pitcher_id,
                    )
                )
                away_lineup_h2h_task_indices[player_id] = len(tasks_to_run) - 1

    if away_pitcher_id and away_pitcher_id != "TBD":
        for player in home_lineup:
            player_id = player.get("id")
            if player_id:
                tasks_to_run.append(
                    mlb_stats_client.get_player_h2h_stats(
                        player_id,
                        away_pitcher_id,
                    )
                )
                home_lineup_h2h_task_indices[player_id] = len(tasks_to_run) - 1

    return tasks_to_run, away_lineup_h2h_task_indices, home_lineup_h2h_task_indices


def _merge_h2h_into_lineup(
    lineup: List[Dict],
    h2h_task_indices: Dict,
    all_results: List,
) -> List[Dict]:
    default_h2h = {"PA": "N/A"}
    lineup_with_h2h = []

    for player in lineup:
        player_copy = player.copy()
        player_id = player_copy.get("id")
        task_index = h2h_task_indices.get(player_id)

        if task_index is not None:
            h2h_result = all_results[task_index]
            if isinstance(h2h_result, Exception):
                player_copy["h2h_stats"] = {"error": str(h2h_result)}
            elif h2h_result is None:
                player_copy["h2h_stats"] = {"error": "Fetch/Parse Failed"}
            else:
                player_copy["h2h_stats"] = h2h_result
        else:
            player_copy["h2h_stats"] = default_h2h.copy()

        lineup_with_h2h.append(player_copy)

    return lineup_with_h2h


def _build_comparison_response(
    ctx: Dict[str, Any],
    away_summary: Dict,
    home_summary: Dict,
    lookback_games: int,
    away_lineup_with_h2h: List[Dict],
    home_lineup_with_h2h: List[Dict],
) -> Dict[str, Any]:
    away_team_id = ctx["away_team_id"]
    home_team_id = ctx["home_team_id"]
    pitcher_details = ctx["pitcher_details"]
    datetime_info = ctx["datetime_info"]

    return {
        "game_info": {
            "game_id": ctx["game_id"],
            "game_datetime": datetime_info.get("dateTime")
            or datetime_info.get("officialDate"),
            "status": ctx["status_info"].get("abstractGameState", "Unknown"),
            "venue": ctx["venue_info"].get("name", "TBD"),
            "away_team": {
                "id": away_team_id,
                "name": TEAM_NAMES.get(
                    away_team_id, ctx["away_team_info"].get("name", "TBD")
                ),
                "record": ctx["away_record_str"],
                "lineup": away_lineup_with_h2h,
                "lineup_status": ctx["away_lineup_status"],
            },
            "home_team": {
                "id": home_team_id,
                "name": TEAM_NAMES.get(
                    home_team_id, ctx["home_team_info"].get("name", "TBD")
                ),
                "record": ctx["home_record_str"],
                "lineup": home_lineup_with_h2h,
                "lineup_status": ctx["home_lineup_status"],
            },
            "away_pitcher": {
                "id": ctx["away_pitcher_id"],
                "name": pitcher_details.get("awayPitcher", "TBD"),
                "hand": pitcher_details.get("awayPitcherHand", "TBD"),
                "season_era": ctx["away_pitcher_era"],
            },
            "home_pitcher": {
                "id": ctx["home_pitcher_id"],
                "name": pitcher_details.get("homePitcher", "TBD"),
                "hand": pitcher_details.get("homePitcherHand", "TBD"),
                "season_era": ctx["home_pitcher_era"],
            },
        },
        "team_comparison": {
            "lookback_games": lookback_games,
            "away": away_summary,
            "home": home_summary,
        },
    }


async def _build_comparison(
    game_id: int,
    lookback_games: int,
    stats_fn: Callable[[int, int, bool], Awaitable[Dict]],
) -> Dict[str, Any]:
    ctx = await _fetch_game_context(game_id)

    h2h_tasks, away_h2h_indices, home_h2h_indices = _build_h2h_tasks(
        ctx["away_lineup"],
        ctx["home_lineup"],
        ctx["away_pitcher_id"],
        ctx["home_pitcher_id"],
    )

    all_tasks = [
        stats_fn(ctx["away_team_id"], lookback_games, False),
        stats_fn(ctx["home_team_id"], lookback_games, False),
    ] + h2h_tasks

    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    away_summary = (
        results[0]
        if not isinstance(results[0], Exception)
        else {"error": str(results[0]), "games_analyzed": 0}
    )
    home_summary = (
        results[1]
        if not isinstance(results[1], Exception)
        else {"error": str(results[1]), "games_analyzed": 0}
    )

    h2h_results = results[2:]

    away_lineup_with_h2h = _merge_h2h_into_lineup(
        ctx["away_lineup"], away_h2h_indices, h2h_results
    )
    home_lineup_with_h2h = _merge_h2h_into_lineup(
        ctx["home_lineup"], home_h2h_indices, h2h_results
    )

    return _build_comparison_response(
        ctx,
        away_summary,
        home_summary,
        lookback_games,
        away_lineup_with_h2h,
        home_lineup_with_h2h,
    )


async def get_game_comparison(game_id: int, lookback_games: int = 10) -> Dict[str, Any]:
    try:
        return await _build_comparison(
            game_id, lookback_games, game_service.get_team_stats_summary
        )
    except Exception as e:
        print(f"Unexpected error in get_game_comparison for game {game_id}: {e}")
        return {"error": f"Failed to generate comparison for game {game_id}: {e}"}


async def get_full_game_comparison(
    game_id: int, lookback_games: int = 10
) -> Dict[str, Any]:
    try:
        return await _build_comparison(
            game_id, lookback_games, game_service.get_team_stats_full_gamesummary
        )
    except Exception as e:
        print(f"Unexpected error in get_full_game_comparison for game {game_id}: {e}")
        return {
            "error": f"Failed to generate full game comparison for game {game_id}: {e}"
        }
