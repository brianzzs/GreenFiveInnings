import asyncio
from typing import Dict, List, Any, Optional

import aiohttp
import statsapi
from async_lru import alru_cache

from app.clients.http_session import get_session

MLB_API_BASE_URL = "https://statsapi.mlb.com/api/v1"


async def _mlb_get(
    path: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    session = await get_session()
    filtered_params = {k: v for k, v in (params or {}).items() if v is not None}
    async with session.get(
        f"{MLB_API_BASE_URL}{path}", params=filtered_params
    ) as response:
        response.raise_for_status()
        return await response.json()


async def _mlb_get_raw(
    url: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    session = await get_session()
    filtered_params = {k: v for k, v in (params or {}).items() if v is not None}
    async with session.get(url, params=filtered_params) as response:
        response.raise_for_status()
        return await response.json()


def get_game_data(game_pk: int) -> Dict[str, Any]:
    try:
        return statsapi.get("game", {"gamePk": game_pk})
    except Exception as e:
        print(f"Error fetching game data for gamePk {game_pk}: {e}")
        raise


async def get_player_stats(
    player_id: int, group: str, type: str, season: Optional[str] = None
) -> str:
    if season:
        url = (
            f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
            f"?stats={type}&group={group}&season={season}"
        )
        try:
            data = await _mlb_get_raw(url)
            stats_list = data.get("stats", [])
            if not stats_list:
                return ""
            splits = stats_list[0].get("splits", [])
            if not splits:
                return ""
            stat = splits[0].get("stat", {})
            return (
                f"Wins: {stat.get('wins', 'TBD')}\n"
                f"Losses: {stat.get('losses', 'TBD')}\n"
                f"ERA: {stat.get('era', 'TBD')}"
            )
        except aiohttp.ClientResponseError as e:
            print(
                f"Error fetching season player stats for player {player_id}, "
                f"season {season}: {e}"
            )
            raise

    params = {"personId": player_id, "group": group, "type": type}
    try:
        return await asyncio.to_thread(statsapi.player_stats, **params)
    except Exception as e:
        print(f"Error fetching player stats for player {player_id}: {e}")
        raise


def lookup_player(query: str) -> List[Dict[str, Any]]:
    try:
        return statsapi.lookup_player(query)
    except Exception as e:
        print(f"Error looking up player with query '{query}': {e}")
        raise


async def lookup_player_async(query: str) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(lookup_player, query)


@alru_cache(maxsize=512)
async def get_player_h2h_stats(
    batter_id: int, pitcher_id: int
) -> Optional[Dict[str, Any]]:
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats?stats=vsTeamTotal&group=hitting&opposingPlayerId={pitcher_id}&language=en"

    try:
        data = await _mlb_get_raw(url)

        stats_list = data.get("stats", [])
        if not stats_list:
            return {"PA": 0}

        total_stats_data = None
        for stat_entry in stats_list:
            stat_type = stat_entry.get("type", {})
            if stat_type and stat_type.get("displayName") == "vsTeamTotal":
                total_stats_data = stat_entry
                break

        if not total_stats_data:
            return {"PA": 0}

        splits = total_stats_data.get("splits", [])
        if not splits:
            return {"PA": 0}

        raw_stats = splits[0].get("stat", {})
        if not raw_stats or raw_stats.get("plateAppearances", 0) == 0:
            return {"PA": 0}
        return {
            "PA": raw_stats.get("plateAppearances"),
            "AB": raw_stats.get("atBats"),
            "H": raw_stats.get("hits"),
            "2B": raw_stats.get("doubles"),
            "3B": raw_stats.get("triples"),
            "HR": raw_stats.get("homeRuns"),
            "RBI": raw_stats.get("rbi"),
            "BB": raw_stats.get("baseOnBalls"),
            "SO": raw_stats.get("strikeOuts"),
            "AVG": raw_stats.get("avg"),
            "OBP": raw_stats.get("obp"),
            "SLG": raw_stats.get("slg"),
            "OPS": raw_stats.get("ops"),
        }

    except asyncio.TimeoutError:
        print(
            f"Timeout fetching H2H stats for batter {batter_id} vs pitcher {pitcher_id}"
        )
        return None
    except aiohttp.ClientResponseError as e:
        status_code = e.status
        print(
            f"Error fetching H2H stats for batter {batter_id} vs pitcher {pitcher_id} (Status: {status_code}): {e}"
        )
        if status_code == 404:
            return {"error": "Not Found"}
        return None
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        print(
            f"Error parsing H2H JSON for batter {batter_id} vs pitcher {pitcher_id}: {e}"
        )
        return None


def get_schedule(
    start_date: str, end_date: Optional[str] = None, team_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    params = {"start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    if team_id:
        params["team"] = team_id
    try:
        return statsapi.schedule(**params)
    except Exception as e:
        print(f"Error fetching schedule with params {params}: {e}")
        raise


async def get_player_info_with_stats(player_id: int, season: str) -> Dict[str, Any]:
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group=[hitting,pitching],type=[season],season={season})"
    try:
        return await _mlb_get_raw(url)
    except aiohttp.ClientResponseError as e:
        print(
            f"Error fetching player info/stats for player {player_id}, season {season}: {e}"
        )
        raise


def get_player_stat_data(player_id: int, group: str, type: str) -> Dict[str, Any]:
    params = {"personId": player_id, "group": group, "type": type}
    try:
        return statsapi.player_stat_data(**params)
    except Exception as e:
        print(
            f"Error fetching player stat data for player {player_id}, group {group}, type {type}: {e}"
        )
        raise


async def get_player_stat_data_async(
    player_id: int, group: str, type: str
) -> Dict[str, Any]:
    return await asyncio.to_thread(get_player_stat_data, player_id, group, type)


async def get_standings(
    league_id: str = "103,104",
    date: Optional[str] = None,
    season: Optional[str] = None,
) -> Dict:
    params = {
        "leagueId": league_id,
        "season": season,
        "standingsTypes": "regularSeason",
        "hydrate": "team(division)",
        "fields": (
            "records,standingsType,teamRecords,team,name,division,id,"
            "nameShort,abbreviation,divisionRank,gamesBack,wildCardRank,"
            "wildCardGamesBack,wildCardEliminationNumber,divisionGamesBack,"
            "clinched,eliminationNumber,winningPercentage,type,wins,losses,"
            "leagueRank,sportRank"
        ),
    }
    if date:
        params["date"] = date
    try:
        payload = await _mlb_get_raw(
            "https://statsapi.mlb.com/api/v1/standings",
            params={k: v for k, v in params.items() if v is not None},
        )

        divisions = {}
        for record in payload.get("records", []):
            for team_record in record.get("teamRecords", []):
                division = team_record.get("team", {}).get("division", {})
                division_id = division.get("id")
                if division_id is None:
                    continue

                if division_id not in divisions:
                    divisions[division_id] = {
                        "div_name": division.get("name", "Unknown"),
                        "teams": [],
                    }

                divisions[division_id]["teams"].append(
                    {
                        "name": team_record.get("team", {}).get("name"),
                        "div_rank": team_record.get("divisionRank"),
                        "w": team_record.get("wins"),
                        "l": team_record.get("losses"),
                        "gb": team_record.get("gamesBack"),
                        "wc_rank": team_record.get("wildCardRank", "-"),
                        "wc_gb": team_record.get("wildCardGamesBack", "-"),
                        "wc_elim_num": team_record.get(
                            "wildCardEliminationNumber", "-"
                        ),
                        "elim_num": team_record.get("eliminationNumber", "-"),
                        "team_id": team_record.get("team", {}).get("id"),
                        "league_rank": team_record.get("leagueRank", "-"),
                        "sport_rank": team_record.get("sportRank", "-"),
                    }
                )

        return divisions
    except Exception as e:
        print(f"Error fetching standings data with params {params}: {e}")
        raise


async def get_schedule_async(
    start_date: str, end_date: Optional[str] = None, team_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(get_schedule, start_date, end_date, team_id)


@alru_cache(maxsize=128)
async def get_game_data_async(game_pk: int) -> Dict[str, Any]:
    return await asyncio.to_thread(get_game_data, game_pk)
