import asyncio
from typing import Dict, List, Any, Optional
from app.clients import mlb_stats_client
from cache import GAME_CACHE
from app.services import schedule_service
from app.utils.calculations import (
    TEAM_NAMES,
    calculate_win_percentage,
)


def fetch_and_cache_linescore(game_id: int) -> List[Dict]:
    """Fetches linescore data for a given game ID."""
    game = mlb_stats_client.get_game_data(game_pk=game_id)
    live_data = game.get("liveData", {})
    linescore = live_data.get("linescore", {})
    innings = linescore.get("innings", [])
    return innings


async def fetch_single_game_details(game_id: int) -> dict:
    """Fetches details for a single game, utilizing cache."""
    cached = GAME_CACHE.get(game_id)
    if cached is not None:
        return cached

    game_data = await mlb_stats_client.get_game_data_async(game_pk=game_id)
    GAME_CACHE.set(game_id, game_data)
    return game_data


async def fetch_game_details_batch(
    game_ids: List[int],
) -> List[dict]:
    """Fetches details for a batch of games concurrently, utilizing cache."""
    tasks = [fetch_single_game_details(game_id) for game_id in game_ids]
    results = await asyncio.gather(*tasks)
    return [res for res in results if res is not None]


def get_processed_game_data(game_id: int) -> Dict:
    """Fetches and processes basic game data for a given game ID."""
    try:
        game = mlb_stats_client.get_game_data(game_pk=game_id)

        live_data = game.get("liveData", {})
        linescore = live_data.get("linescore", {})
        innings = linescore.get("innings", [])
        game_data = game.get("gameData", {})
        teams_data = game_data.get("teams", {})
        away_team_data = teams_data.get("away", {})
        home_team_data = teams_data.get("home", {})
        datetime_data = game_data.get("datetime", {})
        probable_pitchers = game_data.get("probablePitchers", {})
        away_pitcher_data = probable_pitchers.get("away", {})
        home_pitcher_data = probable_pitchers.get("home", {})

        away_team_id = away_team_data.get("id")
        home_team_id = home_team_data.get("id")
        game_datetime = datetime_data.get("dateTime")
        game_date = datetime_data.get("originalDate")
        away_pitcher_id = away_pitcher_data.get("id")
        home_pitcher_id = home_pitcher_data.get("id")

        away_team_runs = sum(
            inning.get("away", {}).get("runs", 0) for inning in innings
        )
        home_team_runs = sum(
            inning.get("home", {}).get("runs", 0) for inning in innings
        )

        return {
            "game_id": game_id,
            "away_team_id": away_team_id,
            "home_team_id": home_team_id,
            "game_datetime": game_datetime,
            "away_team_runs": away_team_runs,
            "home_team_runs": home_team_runs,
            "away_pitcher_id": away_pitcher_id,
            "home_pitcher_id": home_pitcher_id,
            "game_date": game_date,
        }

    except Exception as e:
        print(f"Error fetching or processing game data for game ID {game_id}: {e}")
        return None


def _build_empty_team_stats_summary(
    include_details: bool,
    over_thresholds: List[float],
    error: str = None,
    game_total_thresholds: Optional[List[float]] = None,
    run_line_thresholds: Optional[List[float]] = None,
) -> Dict[str, Any]:
    return_data = {
        "games_analyzed": 0,
        "nrfi": 0.0,
        "game_nrfi_percentage": 0.0,
        "win_percentage": 0.0,
        "overs": {threshold: 0.0 for threshold in over_thresholds},
    }
    if game_total_thresholds:
        return_data["game_totals"] = {
            threshold: 0.0 for threshold in game_total_thresholds
        }
    if run_line_thresholds:
        return_data["run_lines"] = {threshold: 0.0 for threshold in run_line_thresholds}
    if error:
        return_data["error"] = error
    if include_details:
        return_data["results"] = []
    return return_data


def _format_team_stats_summary(
    summary: Dict[str, Any],
    *,
    win_key: str,
    over_key_map: Dict[float, str],
    game_total_key_map: Optional[Dict[float, str]] = None,
    run_line_key_map: Optional[Dict[float, str]] = None,
) -> Dict[str, Any]:
    return_data = {
        "games_analyzed": summary.get("games_analyzed", 0),
        "nrfi": summary.get("nrfi", 0.0),
        "game_nrfi_percentage": summary.get("game_nrfi_percentage", 0.0),
        win_key: summary.get("win_percentage", 0.0),
    }

    overs = summary.get("overs", {})
    for threshold, response_key in over_key_map.items():
        return_data[response_key] = overs.get(threshold, 0.0)

    if game_total_key_map:
        game_totals = summary.get("game_totals", {})
        for threshold, response_key in game_total_key_map.items():
            return_data[response_key] = game_totals.get(threshold, 0.0)

    if run_line_key_map:
        run_lines = summary.get("run_lines", {})
        for threshold, response_key in run_line_key_map.items():
            return_data[response_key] = run_lines.get(threshold, 0.0)

    if "error" in summary:
        return_data["error"] = summary["error"]
    if "results" in summary:
        return_data["results"] = summary["results"]

    return return_data


async def _get_team_stats_summary_by_innings(
    team_id: int,
    num_games: int,
    include_details: bool = False,
    *,
    innings_amount: Optional[int],
    over_thresholds: List[float],
    game_total_thresholds: Optional[List[float]] = None,
    run_line_thresholds: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Fetches the last N completed games and calculates stats for the requested inning window."""
    try:
        game_ids = await schedule_service.fetch_last_n_completed_game_ids(
            team_id, num_games
        )

        if not game_ids:
            return _build_empty_team_stats_summary(
                include_details,
                over_thresholds,
                game_total_thresholds=game_total_thresholds,
                run_line_thresholds=run_line_thresholds,
            )

        game_details = await fetch_game_details_batch(game_ids)
        valid_game_details = [
            gd
            for gd in game_details
            if gd and gd.get("gameData") and gd.get("liveData")
        ]

        if not valid_game_details:
            return _build_empty_team_stats_summary(
                include_details,
                over_thresholds,
                game_total_thresholds=game_total_thresholds,
                run_line_thresholds=run_line_thresholds,
            )

        game_nrfi_list = []
        team_nrfi_list = []
        team_runs_by_window_list = []
        game_total_list = []
        run_line_diffs = []
        moneyline_results_for_calc = []
        detailed_game_results = [] if include_details else None
        games_processed_count = 0

        for game in valid_game_details:
            game_pk = game.get("gameData", {}).get("game", {}).get("pk", "Unknown PK")
            live_data = game.get("liveData", {})
            linescore = live_data.get("linescore")

            if (
                not linescore
                or not linescore.get("innings")
                or not isinstance(linescore.get("innings"), list)
                or len(linescore["innings"]) == 0
            ):
                continue

            innings = linescore["innings"]
            game_data = game.get("gameData", {})
            teams_data = game_data.get("teams", {})
            away_team_data = teams_data.get("away", {})
            home_team_data = teams_data.get("home", {})
            datetime_data = game_data.get("datetime", {})
            probable_pitchers = game_data.get("probablePitchers", {})
            away_pitcher = probable_pitchers.get(
                "away", {"fullName": "TBD", "id": "TBD"}
            )
            home_pitcher = probable_pitchers.get(
                "home", {"fullName": "TBD", "id": "TBD"}
            )
            away_pitcher_hand = "TBD"
            home_pitcher_hand = "TBD"

            if not away_team_data.get("id") or not home_team_data.get("id"):
                continue

            games_processed_count += 1
            is_home_team = home_team_data.get("id") == team_id

            final_scores = linescore.get("teams", {})
            full_away_runs = final_scores.get("away", {}).get("runs")
            full_home_runs = final_scores.get("home", {}).get("runs")

            first_inning = innings[0]
            fi_home_runs = first_inning.get("home", {}).get("runs")
            fi_away_runs = first_inning.get("away", {}).get("runs")
            if fi_home_runs is not None and fi_away_runs is not None:
                game_nrfi_list.append(fi_home_runs == 0 and fi_away_runs == 0)
                team_nrfi_list.append(
                    fi_home_runs == 0 if is_home_team else fi_away_runs == 0
                )

            innings_window = (
                innings if innings_amount is None else innings[:innings_amount]
            )
            window_size = len(innings_window)
            away_total_runs = 0
            home_total_runs = 0
            away_runs_by_inning = [None] * window_size
            home_runs_by_inning = [None] * window_size
            away_runs_found = False
            home_runs_found = False
            team_runs = 0
            team_runs_found = False

            for i, inning in enumerate(innings_window):
                away_inning_runs = inning.get("away", {}).get("runs")
                home_inning_runs = inning.get("home", {}).get("runs")

                if away_inning_runs is not None:
                    away_total_runs += away_inning_runs
                    away_runs_by_inning[i] = away_inning_runs
                    away_runs_found = True
                if home_inning_runs is not None:
                    home_total_runs += home_inning_runs
                    home_runs_by_inning[i] = home_inning_runs
                    home_runs_found = True

                team_inning_runs = (
                    home_inning_runs if is_home_team else away_inning_runs
                )
                if team_inning_runs is not None:
                    team_runs += team_inning_runs
                    team_runs_found = True

            if team_runs_found:
                team_runs_by_window_list.append(team_runs)

            if away_runs_found and home_runs_found:
                moneyline_results_for_calc.append(
                    {
                        "away_team": {
                            "id": away_team_data.get("id"),
                            "total_runs": away_total_runs,
                        },
                        "home_team": {
                            "id": home_team_data.get("id"),
                            "total_runs": home_total_runs,
                        },
                    }
                )
                if game_total_thresholds:
                    game_total_list.append(away_total_runs + home_total_runs)
                if run_line_thresholds:
                    team_total = home_total_runs if is_home_team else away_total_runs
                    opp_total = away_total_runs if is_home_team else home_total_runs
                    run_line_diffs.append(team_total - opp_total)

            if include_details:
                detailed_game_results.append(
                    {
                        "game_date": datetime_data.get("originalDate", "TBD"),
                        "game_pk": game_pk,
                        "away_team": {
                            "id": away_team_data.get("id"),
                            "name": TEAM_NAMES.get(away_team_data.get("id"), "TBD"),
                            "runs": [
                                r if r is not None else "N/A"
                                for r in away_runs_by_inning
                            ],
                            "total_runs": away_total_runs,
                            "full_game_runs": full_away_runs,
                            "probable_pitcher": {
                                "name": away_pitcher.get("fullName", "TBD"),
                                "id": away_pitcher.get("id", "TBD"),
                                "hand": away_pitcher_hand,
                            },
                        },
                        "home_team": {
                            "id": home_team_data.get("id"),
                            "name": TEAM_NAMES.get(home_team_data.get("id"), "TBD"),
                            "runs": [
                                r if r is not None else "N/A"
                                for r in home_runs_by_inning
                            ],
                            "total_runs": home_total_runs,
                            "full_game_runs": full_home_runs,
                            "probable_pitcher": {
                                "name": home_pitcher.get("fullName", "TBD"),
                                "id": home_pitcher.get("id", "TBD"),
                                "hand": home_pitcher_hand,
                            },
                        },
                    }
                )

        game_nrfi_percentage_calc = (
            sum(1 for did_happen in game_nrfi_list if did_happen)
            / len(game_nrfi_list)
            * 100
            if game_nrfi_list
            else 0.0
        )
        team_nrfi_percentage_calc = (
            sum(1 for did_happen in team_nrfi_list if did_happen)
            / len(team_nrfi_list)
            * 100
            if team_nrfi_list
            else 0.0
        )
        over_percentages = {
            threshold: (
                sum(1 for runs in team_runs_by_window_list if runs >= threshold)
                / len(team_runs_by_window_list)
                * 100
                if team_runs_by_window_list
                else 0.0
            )
            for threshold in over_thresholds
        }
        win_percentage_calc = calculate_win_percentage(
            moneyline_results_for_calc, team_id
        )

        return_data = {
            "games_analyzed": games_processed_count,
            "nrfi": round(team_nrfi_percentage_calc, 2),
            "game_nrfi_percentage": round(game_nrfi_percentage_calc, 2),
            "win_percentage": round(win_percentage_calc, 2),
            "overs": {
                threshold: round(value, 2)
                for threshold, value in over_percentages.items()
            },
        }

        if game_total_thresholds:
            game_total_percentages = {
                threshold: (
                    sum(1 for total in game_total_list if total >= threshold)
                    / len(game_total_list)
                    * 100
                    if game_total_list
                    else 0.0
                )
                for threshold in game_total_thresholds
            }
            return_data["game_totals"] = {
                threshold: round(value, 2)
                for threshold, value in game_total_percentages.items()
            }

        if run_line_thresholds:
            run_line_percentages = {
                threshold: (
                    sum(1 for d in run_line_diffs if d >= threshold)
                    / len(run_line_diffs)
                    * 100
                    if run_line_diffs
                    else 0.0
                )
                for threshold in run_line_thresholds
            }
            return_data["run_lines"] = {
                threshold: round(value, 2)
                for threshold, value in run_line_percentages.items()
            }

        if include_details:
            detailed_game_results.sort(
                key=lambda x: x.get("game_date", "0000-00-00"), reverse=True
            )
            return_data["results"] = detailed_game_results

        return return_data

    except Exception as e:
        print(
            f"Error calculating team stats summary for team {team_id} over last {num_games} games: {e}"
        )
        import traceback

        traceback.print_exc()
        return _build_empty_team_stats_summary(
            include_details,
            over_thresholds,
            error=f"Error calculating stats: {str(e)}",
            game_total_thresholds=game_total_thresholds,
            run_line_thresholds=run_line_thresholds,
        )


async def get_team_stats_summary(
    team_id: int, num_games: int, include_details: bool = False
) -> Dict:
    summary = await _get_team_stats_summary_by_innings(
        team_id,
        num_games,
        include_details,
        innings_amount=5,
        over_thresholds=[1.5, 2.5],
    )
    return _format_team_stats_summary(
        summary,
        win_key="win_percentage_f5",
        over_key_map={
            1.5: "over1_5F5",
            2.5: "over2_5F5",
        },
    )


async def get_team_stats_full_gamesummary(
    team_id: int, num_games: int, include_details: bool = False
) -> Dict:
    summary = await _get_team_stats_summary_by_innings(
        team_id,
        num_games,
        include_details,
        innings_amount=None,
        over_thresholds=[3.5, 4.5, 5.5],
        game_total_thresholds=[5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
        run_line_thresholds=[-2.5, -1.5, 1.5, 2.5],
    )
    return _format_team_stats_summary(
        summary,
        win_key="win_percentage_f9",
        over_key_map={
            3.5: "over3_5F9",
            4.5: "over4_5F9",
            5.5: "over5_5F9",
        },
        game_total_key_map={
            5.5: "game_over5_5",
            6.5: "game_over6_5",
            7.5: "game_over7_5",
            8.5: "game_over8_5",
            9.5: "game_over9_5",
            10.5: "game_over10_5",
        },
        run_line_key_map={
            -2.5: "rl_plus_2_5",
            -1.5: "rl_plus_1_5",
            1.5: "rl_minus_1_5",
            2.5: "rl_minus_2_5",
        },
    )
