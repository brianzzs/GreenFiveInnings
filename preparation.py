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


def get_game_details(game_id):
    game = statsapi.get("game", {"gamePk": game_id})
    return game


def parse_stats(stats_string):
    lines = stats_string.split("\n")
    stats = {}

    for line in lines:
        parts = line.split(": ")
        if len(parts) == 2:
            key, value = parts
            stats[key] = value

    pitcher_stats = {
        "wins": stats.get("wins", "Unknown"),
        "losses": stats.get("losses", "Unknown"),
        "era": stats.get("era", "Unknown")
    }

    return pitcher_stats


def get_pitchers_info(data):
    probable_pitchers = data['gameData']['probablePitchers']
    players = data['gameData']['players']

    home_pitcher = probable_pitchers.get('home', {'fullName': 'TBD', 'id': 'TBD'})
    away_pitcher = probable_pitchers.get('away', {'fullName': 'TBD', 'id': 'TBD'})

    home_pitcher_hand = players.get('ID' + str(home_pitcher['id']), {'pitchHand': {'code': 'Unknown'}})['pitchHand']['code']
    away_pitcher_hand = players.get('ID' + str(away_pitcher['id']), {'pitchHand': {'code': 'Unknown'}})['pitchHand']['code']

    try:
        home_pitcher_stats = statsapi.player_stats(home_pitcher['id'], group="pitching", type="season")
        home_pitcher_stats = parse_stats(home_pitcher_stats)
    except Exception:
        home_pitcher_stats = {'wins': 'TBD', 'losses': 'TBD', 'era': 'TBD'}

    try:
        away_pitcher_stats = statsapi.player_stats(away_pitcher['id'], group="pitching", type="season")
        away_pitcher_stats = parse_stats(away_pitcher_stats)
    except Exception:
        away_pitcher_stats = {'wins': 'TBD', 'losses': 'TBD', 'era': 'TBD'}

    pitcher_info = {
        "homePitcherID": home_pitcher['id'],
        "homePitcher": home_pitcher['fullName'],
        "homePitcherHand": home_pitcher_hand,
        "homePitcherWins": home_pitcher_stats['wins'],
        "homePitcherLosses": home_pitcher_stats['losses'],
        "homePitcherERA": home_pitcher_stats['era'],
        "awayPitcherID": away_pitcher['id'],
        "awayPitcher": away_pitcher['fullName'],
        "awayPitcherHand": away_pitcher_hand,
        "awayPitcherWins": away_pitcher_stats['wins'],
        "awayPitcherLosses": away_pitcher_stats['losses'],
        "awayPitcherERA": away_pitcher_stats['era']
    }

    return pitcher_info




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

    if not next_games:
        start_date = today + datetime.timedelta(days=1)
        formatted_start_date = start_date.strftime("%m/%d/%Y")
        if(team_id == 0):
            next_games = statsapi.schedule(start_date=formatted_start_date)
        else:
            next_games = statsapi.schedule(start_date=formatted_start_date, team=team_id)

    games_with_pitcher_info = []
    for game in next_games:
        game_details = get_game_details(game['game_id'])
        pitcher_info = get_pitchers_info(game_details)

        game_with_pitcher_info = {
            'game_id': game['game_id'],
            'game_datetime': datetime.datetime.strptime(game['game_datetime'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d %H:%M:%S'),
            'away_team': {
                'name': game['away_name'],
                'id': game['away_id'],
                'wins': game_details['gameData']['teams']['away']['record']['wins'],
                'losses': game_details['gameData']['teams']['away']['record']['losses'],
                'probable_pitcher': {
                    'name': game['away_probable_pitcher'] if game['away_probable_pitcher'] else 'TBD',
                    'id': pitcher_info['awayPitcherID'],
                    'hand': pitcher_info['awayPitcherHand'],
                    'wins': pitcher_info['awayPitcherWins'],
                    'losses': pitcher_info['awayPitcherLosses'],
                    'era': pitcher_info['awayPitcherERA'],
                },
            },
            'home_team': {
                'name': game['home_name'],
                'id': game['home_id'],
                'wins': game_details['gameData']['teams']['home']['record']['wins'],
                'losses': game_details['gameData']['teams']['home']['record']['losses'],
                'probable_pitcher': {
                    'name': game['home_probable_pitcher'] if game['home_probable_pitcher'] else 'TBD',
                    'id': pitcher_info['homePitcherID'],
                    'hand': pitcher_info['homePitcherHand'],
                    'wins': pitcher_info['homePitcherWins'],
                    'losses': pitcher_info['homePitcherLosses'],
                    'era': pitcher_info['homePitcherERA'],
                },
            },
        }
        games_with_pitcher_info.append(game_with_pitcher_info)

    return games_with_pitcher_info



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
