import datetime
import statsapi
from typing import List
from cache import (
    fetch_and_cache_linescore,
    fetch_game_data,
    fetch_and_cache_pitcher_info,
)

TEAM_NAMES = {
    109: "ARI D-backs",
    144: "ATL Braves",
    110: "BAL Orioles",
    111: "BOS Red Sox",
    112: "CHC Cubs",
    113: "CIN Reds",
    114: "CLE Guardians",
    115: "COL Rockies",
    116: "DET Tigers",
    117: "HOU Astros",
    118: "KC Royals",
    108: "LAA Angels",
    119: "LAD Dodgers",
    146: "MIA Marlins",
    158: "MIL Brewers",
    142: "MIN Twins",
    121: "NYM Mets",
    147: "NYY Yankees",
    133: "OAK Athletics",
    143: "PHI Phillies",
    134: "PIT Pirates",
    135: "SD Padres",
    136: "SEA Mariners",
    137: "SF Giants",
    138: "STL Cardinals",
    139: "TB Rays",
    140: "TEX Rangers",
    141: "TOR Blue Jays",
    145: "CWS White Sox",
    120: "WSH Nationals",
}


def get_ml_results(game_id):
    linescore_data = fetch_and_cache_linescore(game_id)
    game_data = fetch_game_data(game_id)

    first_5_innings = linescore_data[:5]

    runs_home_team = [inning["home"]["runs"] for inning in first_5_innings]
    runs_away_team = [inning["away"]["runs"] for inning in first_5_innings]

    home_team_id = game_data["home_team_id"]
    home_team_name = TEAM_NAMES.get(home_team_id, "Unknown Team")
    away_team_id = game_data["away_team_id"]
    away_team_name = TEAM_NAMES.get(away_team_id, "Unknown Team")

    final_runs_home_team = sum(runs_home_team)
    final_runs_away_team = sum(runs_away_team)

    pitcher_info = fetch_and_cache_pitcher_info(game_id)

    return {
        "away_team": {
            "name": away_team_name,
            "id": away_team_id,
            "runs": runs_away_team,
            "total_runs": final_runs_away_team,
            "probable_pitcher": {
                "name": pitcher_info["awayPitcher"],
                "id": pitcher_info["awayPitcherID"],
                "hand": pitcher_info["awayPitcherHand"],
            },
        },
        "home_team": {
            "name": home_team_name,
            "id": home_team_id,
            "runs": runs_home_team,
            "total_runs": final_runs_home_team,
            "probable_pitcher": {
                "name": pitcher_info["homePitcher"],
                "id": pitcher_info["homePitcherID"],
                "hand": pitcher_info["homePitcherHand"],
            },
        },
    }


def calculate_win_percentage(results: List[dict], team_id: int) -> float:
    team_games = [(game, game["away_team"]["id"] == team_id) for game in results]
    wins = sum(
        1
        for game, is_away in team_games
        if (is_away and game["away_team"]["runs"] > game["home_team"]["runs"])
        or (not is_away and game["home_team"]["runs"] > game["away_team"]["runs"])
    )
    return (wins / len(results) * 100) if results else 0


def get_first_inning(game_id, team_id):
    linescore_data = fetch_and_cache_linescore(game_id)
    game_data = fetch_game_data(game_id)

    first_inning = linescore_data[:1]

    runs_scored = sum(
        (
            inning["home"]["runs"]
            if game_data["home_team_id"] == team_id
            else inning["away"]["runs"] if game_data["away_team_id"] == team_id else 0
        )
        for inning in first_inning
    )
    return runs_scored


def calculate_nrfi_occurrence(list_of_runs):
    qualified_games = sum(1 for runs in list_of_runs if runs == 0)
    total_games = len(list_of_runs)
    occurrence_percentage = (qualified_games / total_games) * 100
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage


def get_team_box_score_first_five(game_id, team_id):
    linescore_data = fetch_and_cache_linescore(game_id)
    game_data = fetch_game_data(game_id)
    first_5_innings = linescore_data[:5]

    runs_scored = sum(
        (
            inning["home"]["runs"]
            if game_data["home_team_id"] == team_id
            else (inning["away"]["runs"] if game_data["away_team_id"] == team_id else 0)
        )
        for inning in first_5_innings
    )

    return runs_scored


def calculate_team_total_run_occurrence_percentage_5_innings(list_of_runs, min_runs):
    qualified_games = sum(1 for runs in list_of_runs if runs >= min_runs)
    total_games = len(list_of_runs)
    occurrence_percentage = (qualified_games / total_games) * 100
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage
