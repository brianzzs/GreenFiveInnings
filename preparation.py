import datetime
import statsapi
import pytz
from calculations import (
    TEAM_NAMES,
    get_ml_results,
    calculate_win_percentage,
    get_first_inning,
    calculate_nrfi_occurrence,
    get_team_box_score_first_five,
    calculate_team_total_run_occurrence_percentage_5_innings,
    fetch_and_cache_pitcher_info,
)
from functools import lru_cache
from cache import fetch_and_cache_game_ids_span


def convert_utc_to_local(utc_datetime_str):
    utc_dt = datetime.datetime.strptime(utc_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
    utc_dt = pytz.UTC.localize(utc_dt)
    local_tz = pytz.timezone('America/New_York')  # Using Eastern Time as default
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def get_game_details(game_id):
    game = statsapi.get("game", {"gamePk": game_id})
    return game


async def get_nrfi_occurence(team_id, num_days):
    first_inning_list = []
    game_ids = await fetch_and_cache_game_ids_span(team_id, num_days)
    for game_id in game_ids:
        runs_first_inning = get_first_inning(game_id, team_id)
        first_inning_list.append(runs_first_inning)

    nrfi_occurence = calculate_nrfi_occurrence(first_inning_list)
    return nrfi_occurence

@lru_cache(maxsize=128)
def get_today_schedule():
    base_date = datetime.date.today()
    formatted_date = base_date.strftime("%m/%d/%Y")

    next_games = statsapi.schedule(start_date=formatted_date, end_date=formatted_date)

    if not next_games:
        return []

    games_with_pitcher_info = []
    for game in next_games:
        game_details = get_game_details(game["game_id"])
        pitcher_info = fetch_and_cache_pitcher_info(game["game_id"], game_details)

        game_with_pitcher_info = {
            "game_id": game["game_id"],
            "game_datetime": convert_utc_to_local(game["game_datetime"]),
            "away_team": {
                "name": game["away_name"],
                "id": game["away_id"],
                "wins": game_details["gameData"]["teams"]["away"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["away"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["away_probable_pitcher"] if game["away_probable_pitcher"] else "TBD",
                    "id": pitcher_info["awayPitcherID"],
                    "hand": pitcher_info["awayPitcherHand"],
                    "wins": pitcher_info["awayPitcherWins"],
                    "losses": pitcher_info["awayPitcherLosses"],
                    "era": pitcher_info["awayPitcherERA"],
                },
            },
            "home_team": {
                "name": game["home_name"],
                "id": game["home_id"],
                "wins": game_details["gameData"]["teams"]["home"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["home"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["home_probable_pitcher"] if game["home_probable_pitcher"] else "TBD",
                    "id": pitcher_info["homePitcherID"],
                    "hand": pitcher_info["homePitcherHand"],
                    "wins": pitcher_info["homePitcherWins"],
                    "losses": pitcher_info["homePitcherLosses"],
                    "era": pitcher_info["homePitcherERA"],
                },
            },
        }
        games_with_pitcher_info.append(game_with_pitcher_info)

    return games_with_pitcher_info

@lru_cache(maxsize=128)
def schedule(team_id, num_days=None):
    base_date = datetime.date.today()

    if num_days is not None:
        start_date = base_date - datetime.timedelta(days=num_days)
        formatted_start_date = start_date.strftime("%m/%d/%Y")
    else:
        formatted_start_date = base_date.strftime("%m/%d/%Y")

    formatted_end_date = base_date.strftime("%m/%d/%Y")

    next_games = statsapi.schedule(
        start_date=formatted_start_date, end_date=formatted_end_date, team=team_id
    )

    if not next_games:
        start_date = base_date + datetime.timedelta(days=1)
        formatted_start_date = start_date.strftime("%m/%d/%Y")
        next_games = statsapi.schedule(
            start_date=formatted_start_date, team=team_id
        )

    games_with_pitcher_info = []
    for game in next_games:
        game_details = get_game_details(game["game_id"])
        pitcher_info = fetch_and_cache_pitcher_info(game["game_id"], game_details)

        game_with_pitcher_info = {
            "game_id": game["game_id"],
            "game_datetime": convert_utc_to_local(game["game_datetime"]),
            "away_team": {
                "name": game["away_name"],
                "id": game["away_id"],
                "wins": game_details["gameData"]["teams"]["away"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["away"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["away_probable_pitcher"] if game["away_probable_pitcher"] else "TBD",
                    "id": pitcher_info["awayPitcherID"],
                    "hand": pitcher_info["awayPitcherHand"],
                    "wins": pitcher_info["awayPitcherWins"],
                    "losses": pitcher_info["awayPitcherLosses"],
                    "era": pitcher_info["awayPitcherERA"],
                },
            },
            "home_team": {
                "name": game["home_name"],
                "id": game["home_id"],
                "wins": game_details["gameData"]["teams"]["home"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["home"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["home_probable_pitcher"] if game["home_probable_pitcher"] else "TBD",
                    "id": pitcher_info["homePitcherID"],
                    "hand": pitcher_info["homePitcherHand"],
                    "wins": pitcher_info["homePitcherWins"],
                    "losses": pitcher_info["homePitcherLosses"],
                    "era": pitcher_info["homePitcherERA"],
                },
            },
        }
        games_with_pitcher_info.append(game_with_pitcher_info)

    return games_with_pitcher_info


@lru_cache(maxsize=128)
async def get_moneyline_scores_first_5_innings(team_id, num_days):
    game_ids = await fetch_and_cache_game_ids_span(team_id, num_days)
    results = []

    for game_id in game_ids:
        game_result = get_ml_results(game_id)
        results.append(game_result)

    return results


@lru_cache(maxsize=128)
async def get_overs_first_5_innings(team_id, num_days):
    game_ids = await fetch_and_cache_game_ids_span(team_id, num_days)
    runs_per_game = []
    list_of_runs_f5 = []

    for game_id in game_ids:
        list_of_runs_f5 = get_team_box_score_first_five(game_id, team_id)
        runs_per_game.append(list_of_runs_f5)

    occurence_over_1_5 = calculate_team_total_run_occurrence_percentage_5_innings(
        runs_per_game, 1.5
    )
    occurence_over_2_5 = calculate_team_total_run_occurrence_percentage_5_innings(
        runs_per_game, 2.5
    )

    return {"over1_5F5": occurence_over_1_5, "over2_5F5": occurence_over_2_5}


def get_list_of_runs_selected_team(game_id, team_id):
    list_of_runs = []
    runs_scored = get_team_box_score_first_five(game_id, team_id)
    list_of_runs.append(runs_scored)

    return list_of_runs


@lru_cache(maxsize=128)
def get_team_stats(team_id, num_days):
    return {
        "nrfi": get_nrfi_occurence(team_id, num_days),
        "moneyline_scores": get_moneyline_scores_first_5_innings(team_id, num_days),
        "win_percentage": calculate_win_percentage(
            get_moneyline_scores_first_5_innings(team_id, num_days), team_id
        ),
        "overs_first_5_innings": get_overs_first_5_innings(team_id, num_days),
        "list_of_runs": get_list_of_runs_selected_team(team_id, team_id),
    }

@lru_cache(maxsize=128)
def get_next_game_schedule(team_id):
    base_date = datetime.date.today()
    formatted_date = base_date.strftime("%m/%d/%Y")

    if team_id == 0:
        next_games = statsapi.schedule(start_date=formatted_date)
    else:
        next_games = statsapi.schedule(start_date=formatted_date, team=team_id)

    # If no games today, look for tomorrow's games
    if not next_games:
        next_date = base_date + datetime.timedelta(days=1)
        formatted_date = next_date.strftime("%m/%d/%Y")
        if team_id == 0:
            next_games = statsapi.schedule(start_date=formatted_date)
        else:
            next_games = statsapi.schedule(start_date=formatted_date, team=team_id)

    if not next_games:
        return []

    games_with_pitcher_info = []
    for game in next_games:
        game_details = get_game_details(game["game_id"])
        pitcher_info = fetch_and_cache_pitcher_info(game["game_id"], game_details)

        game_with_pitcher_info = {
            "game_id": game["game_id"],
            "game_datetime": convert_utc_to_local(game["game_datetime"]),
            "away_team": {
                "name": game["away_name"],
                "id": game["away_id"],
                "wins": game_details["gameData"]["teams"]["away"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["away"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["away_probable_pitcher"] if game["away_probable_pitcher"] else "TBD",
                    "id": pitcher_info["awayPitcherID"],
                    "hand": pitcher_info["awayPitcherHand"],
                    "wins": pitcher_info["awayPitcherWins"],
                    "losses": pitcher_info["awayPitcherLosses"],
                    "era": pitcher_info["awayPitcherERA"],
                },
            },
            "home_team": {
                "name": game["home_name"],
                "id": game["home_id"],
                "wins": game_details["gameData"]["teams"]["home"]["record"]["wins"],
                "losses": game_details["gameData"]["teams"]["home"]["record"]["losses"],
                "probable_pitcher": {
                    "name": game["home_probable_pitcher"] if game["home_probable_pitcher"] else "TBD",
                    "id": pitcher_info["homePitcherID"],
                    "hand": pitcher_info["homePitcherHand"],
                    "wins": pitcher_info["homePitcherWins"],
                    "losses": pitcher_info["homePitcherLosses"],
                    "era": pitcher_info["homePitcherERA"],
                },
            },
        }
        games_with_pitcher_info.append(game_with_pitcher_info)

    return games_with_pitcher_info
