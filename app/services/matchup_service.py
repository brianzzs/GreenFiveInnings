import asyncio
from typing import Dict, List, Any

from app.services import schedule_service
from app.clients import mlb_stats_client
from app.utils import helpers
from app.utils.calculations import TEAM_NAMES
from app import season_context
from cache import get_ttl_cache, set_ttl_cache

BEST_MATCHUPS_CACHE_PREFIX = "best_matchups"
BEST_MATCHUPS_TTL_SECONDS = 60
PLAYER_IMAGE_URL = "https://img.mlbstatic.com/mlb-photos/image/upload/w_213,d_people:generic:headshot:67:current.png,f_auto,q_auto/v1/people/{player_id}/headshot/67/current"


def _parse_avg(value) -> float:
    if value is None:
        return -1.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s in (".---", "---"):
        return -1.0
    try:
        return float(s)
    except (ValueError, TypeError):
        return -1.0


def _sort_key(matchup: Dict) -> tuple:
    return (-_parse_avg(matchup["h2h"]["AVG"]), -(matchup["h2h"]["AB"] or 0))


def _build_matchup(
    batter: Dict,
    pitcher_id: int,
    pitcher_name: str,
    pitcher_team: str,
    pitcher_hand: str,
    game_id: int,
    batter_team: str,
    bat_side: str,
    h2h: Dict,
) -> Dict[str, Any]:
    return {
        "batter": {
            "id": batter["id"],
            "name": batter["name"],
            "team_name": batter_team,
            "bat_side": bat_side,
            "image_url": PLAYER_IMAGE_URL.format(player_id=batter["id"]),
        },
        "pitcher": {
            "id": pitcher_id,
            "name": pitcher_name,
            "team_name": pitcher_team,
            "hand": pitcher_hand,
        },
        "game_id": game_id,
        "h2h": {
            "AB": h2h.get("AB", 0),
            "H": h2h.get("H", 0),
            "HR": h2h.get("HR", 0),
            "RBI": h2h.get("RBI", 0),
            "BB": h2h.get("BB", 0),
            "SO": h2h.get("SO", 0),
            "AVG": h2h.get("AVG", ".---"),
            "OPS": h2h.get("OPS", ".---"),
        },
    }


async def _resolve_lineups(game: Dict) -> tuple:
    game_id = game["game_id"]
    away_lineup = None
    home_lineup = None
    bat_sides: Dict[int, str] = {}

    try:
        game_data = await mlb_stats_client.get_game_data_async(game_id)
        boxscore = game_data.get("liveData", {}).get("boxscore", {})
        away_lineup = helpers.extract_lineup(boxscore, "away")
        home_lineup = helpers.extract_lineup(boxscore, "home")

        for team_key in ("away", "home"):
            players = boxscore.get("teams", {}).get(team_key, {}).get("players", {})
            for player_data in players.values():
                pid = player_data.get("person", {}).get("id")
                side = player_data.get("batSide", {}).get("code")
                if pid and side:
                    bat_sides[pid] = side
    except Exception as e:
        print(f"[matchup_service] Error fetching game data for {game_id}: {e}")

    if away_lineup is None:
        away_lineup = await schedule_service.get_last_game_lineup(game["away_team_id"])
    if home_lineup is None:
        home_lineup = await schedule_service.get_last_game_lineup(game["home_team_id"])

    return away_lineup or [], home_lineup or [], bat_sides


async def get_best_matchups() -> Dict[str, Any]:
    today = season_context.reference_date()
    cache_key = f"{BEST_MATCHUPS_CACHE_PREFIX}:{today.isoformat()}"
    cached = get_ttl_cache(cache_key)
    if cached is not None:
        return cached

    try:
        schedule = await schedule_service.get_today_schedule()
        if not schedule:
            return set_ttl_cache(
                cache_key,
                {"date": today.isoformat(), "total_matchups": 0, "matchups": []},
                BEST_MATCHUPS_TTL_SECONDS,
            )

        all_tasks: List = []
        task_meta: List[Dict] = []

        for game in schedule:
            away_lineup, home_lineup, bat_sides = await _resolve_lineups(game)
            away_pid = game.get("awayPitcherID")
            home_pid = game.get("homePitcherID")
            home_team = TEAM_NAMES.get(
                game["home_team_id"], game.get("home_team_name", "TBD")
            )
            away_team = TEAM_NAMES.get(
                game["away_team_id"], game.get("away_team_name", "TBD")
            )

            if home_pid and home_pid != "TBD":
                for batter in away_lineup:
                    pid = batter.get("id")
                    if pid:
                        all_tasks.append(
                            mlb_stats_client.get_player_h2h_stats(pid, home_pid)
                        )
                        task_meta.append(
                            {
                                "batter": batter,
                                "pitcher_id": home_pid,
                                "pitcher_name": game.get("homePitcher", "TBD"),
                                "pitcher_hand": game.get("homePitcherHand", "TBD"),
                                "pitcher_team": home_team,
                                "batter_team": away_team,
                                "game_id": game["game_id"],
                                "bat_side": bat_sides.get(pid, "N/A"),
                            }
                        )

            if away_pid and away_pid != "TBD":
                for batter in home_lineup:
                    pid = batter.get("id")
                    if pid:
                        all_tasks.append(
                            mlb_stats_client.get_player_h2h_stats(pid, away_pid)
                        )
                        task_meta.append(
                            {
                                "batter": batter,
                                "pitcher_id": away_pid,
                                "pitcher_name": game.get("awayPitcher", "TBD"),
                                "pitcher_hand": game.get("awayPitcherHand", "TBD"),
                                "pitcher_team": away_team,
                                "batter_team": home_team,
                                "game_id": game["game_id"],
                                "bat_side": bat_sides.get(pid, "N/A"),
                            }
                        )

        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        matchups: List[Dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception) or result is None:
                continue
            if isinstance(result, dict) and (
                "error" in result or result.get("PA") == 0
            ):
                continue
            ab = result.get("AB") or 0
            if ab < 2:
                continue

            m = task_meta[i]
            matchups.append(
                _build_matchup(
                    batter=m["batter"],
                    pitcher_id=m["pitcher_id"],
                    pitcher_name=m["pitcher_name"],
                    pitcher_team=m["pitcher_team"],
                    pitcher_hand=m["pitcher_hand"],
                    game_id=m["game_id"],
                    batter_team=m["batter_team"],
                    bat_side=m["bat_side"],
                    h2h=result,
                )
            )

        matchups.sort(key=_sort_key)
        response = {
            "date": today.isoformat(),
            "total_matchups": len(matchups),
            "matchups": matchups,
        }
        return set_ttl_cache(cache_key, response, BEST_MATCHUPS_TTL_SECONDS)

    except Exception as e:
        print(f"[get_best_matchups] Error: {e}")
        return {
            "date": today.isoformat(),
            "total_matchups": 0,
            "matchups": [],
            "error": str(e),
        }
