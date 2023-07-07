import datetime
import statsapi
from calculations import TEAM_NAMES, get_game_ids_last_n_days, get_ml_results, calculate_win_percentage, \
    get_first_inning, calculate_nrfi_occurrence, get_box_score_selected_team_F5, \
    calculate_team_total_run_occurrence_percentage_5_innings


def get_game_ids_last_n_days(team_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    formatted_end_date = end_date.strftime("%m/%d/%Y")
    last_n_days_games = statsapi.schedule(start_date=formatted_start_date, end_date=formatted_end_date, team=team_id)
    return [game['game_id'] for game in last_n_days_games]


def get_nrfi_occurence(team_id, num_days):
    first_inning_list = []
    game_ids = get_game_ids_last_n_days(team_id, num_days)
    for game_id in game_ids:
        runs_first_inning = get_first_inning(game_id, num_days, team_id)
        first_inning_list.append(runs_first_inning)

    nrfi_occurence = calculate_nrfi_occurrence(first_inning_list)
    return nrfi_occurence

def schedule(team_id):
    today = datetime.date.today()
    start_date = today
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    if(team_id == 0):
        next_games = statsapi.schedule(start_date=formatted_start_date)
    else:
        next_games = statsapi.schedule(start_date=formatted_start_date, team=team_id)

    return [
        {
            'game_id': game['game_id'],
            'game_datetime': datetime.datetime.strptime(game['game_datetime'], '%Y-%m-%dT%H:%M:%SZ').strftime(
                '%Y-%m-%d %H:%M:%S'),
            'away_name': game['away_name'],
            'away_id': game['away_id'],
            'away_probable_pitcher': game['away_probable_pitcher'],
            'home_name': game['home_name'],
            'home_id': game['home_id'],
            'home_probable_pitcher': game['home_probable_pitcher']
        }
        for game in next_games
    ]


def get_moneyline_scores_first_5_innings(team_id, num_days):
    game_ids = get_game_ids_last_n_days(team_id, num_days)
    results = []
    for game_id in game_ids:
        game_result = get_ml_results(game_id, num_days)
        results.append(game_result)

    return results


def get_overs_first_5_innings(team_id, num_days):
    game_ids = get_game_ids_last_n_days(team_id, num_days)
    runs_per_game = []
    list_of_runs_f5 = []
    for game_id in game_ids:
        list_of_runs_f5 = get_box_score_selected_team_F5(game_id, team_id, num_days)
        runs_per_game.append(list_of_runs_f5)

    occurence_over_1_5 = calculate_team_total_run_occurrence_percentage_5_innings(runs_per_game, 1.5)
    occurence_over_2_5 = calculate_team_total_run_occurrence_percentage_5_innings(runs_per_game, 2.5)

    return {"over1_5F5": occurence_over_1_5, "over2_5F5": occurence_over_2_5}


def get_list_of_runs_selected_team(game_id, team_id, num_days):
    list_of_runs = []
    runs_scored = get_box_score_selected_team_F5(game_id, team_id, num_days)
    list_of_runs.append(runs_scored)

    return list_of_runs
