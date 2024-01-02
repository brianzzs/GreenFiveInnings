import datetime
import statsapi

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

def get_game_ids_last_n_days(team_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)
   # formatted_start_date = start_date.strftime("%m/%d/%Y")
  #  formatted_end_date = end_date.strftime("%m/%d/%Y")
    formatted_start_date = "09/15/2023"
    formatted_end_date = "10/1/2023"
    last_n_days_games = statsapi.schedule(start_date=formatted_start_date, end_date=formatted_end_date, team=team_id)
    return [game['game_id'] for game in last_n_days_games]


def get_ml_results(game_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)
  #  formatted_start_date = start_date.strftime("%m/%d/%Y")
   # formatted_end_date = end_date.strftime("%m/%d/%Y")
    formatted_start_date = "09/15/2023"
    formatted_end_date = "10/1/2023"
    game = statsapi.get("game", {"gamePk": game_id, "startDate": formatted_start_date, "endDate": formatted_end_date})
    linescore_data = game["liveData"]["linescore"]["innings"]
    first_5_innings = linescore_data[:5]

    runs_home_team = []
    runs_away_team = []

    for inning in first_5_innings:
        home_team_runs = inning['home']['runs']
        away_team_runs = inning['away']['runs']

        runs_home_team.append(home_team_runs)
        runs_away_team.append(away_team_runs)

    home_team_id = game['gameData']['teams']['home']['id']
    home_team_name = TEAM_NAMES.get(home_team_id, "Unknown Team")
    away_team_id = game['gameData']['teams']['away']['id']
    away_team_name = TEAM_NAMES.get(away_team_id, "Unknown Team")

    final_runs_home_team = sum(runs_home_team)
    final_runs_away_team = sum(runs_away_team)

    pitcher_info = get_pitchers_info(game)

    return {
        'away_team': {
            'name': away_team_name,
            'id': away_team_id,
            'runs': runs_away_team,
            'total_runs': final_runs_away_team,
            'probable_pitcher': {
                'name': pitcher_info['awayPitcher'],
                'id': pitcher_info['awayPitcherID'],
                'hand': pitcher_info['awayPitcherHand']
            }
        },
        'home_team': {
            'name': home_team_name,
            'id': home_team_id,
            'runs': runs_home_team,
            'total_runs': final_runs_home_team,
            'probable_pitcher': {
                'name': pitcher_info['homePitcher'],
                'id': pitcher_info['homePitcherID'],
                'hand': pitcher_info['homePitcherHand']
            }
        }
    }


def calculate_win_percentage(results, team_id):
    total_games = 0
    team_wins = 0

    for game in results:
        if game['away_team']['id'] == team_id:
            total_games += 1
            if game['away_team']['total_runs'] > game['home_team']['total_runs']:
                team_wins += 1
        elif game['home_team']['id'] == team_id:
            total_games += 1
            if game['home_team']['total_runs'] > game['away_team']['total_runs']:
                team_wins += 1

    if total_games == 0:
        return 0

    win_percentage = (team_wins / total_games) * 100
    rounded_percentage = round(win_percentage, 2)

    return rounded_percentage



def get_first_inning(game_id, num_days, team_id):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)
  #  formatted_start_date = start_date.strftime("%m/%d/%Y")
  #  formatted_end_date = end_date.strftime("%m/%d/%Y")
    formatted_start_date = "09/15/2023"
    formatted_end_date = "10/1/2023"
    game = statsapi.get("game", {"gamePk": game_id, "startDate": formatted_start_date, "endDate": formatted_end_date})
    linescore_data = game["liveData"]["linescore"]["innings"]
    first_5_innings = linescore_data[:1]

    runs_scored = sum(inning['home']['runs'] if game['gameData']['teams']['home']['id'] == team_id
                      else inning['away']['runs'] if game['gameData']['teams']['away']['id'] == team_id
    else 0
                      for inning in first_5_innings)

    return runs_scored


def calculate_nrfi_occurrence(list_of_runs):
    qualified_games = sum(1 for runs in list_of_runs if runs == 0)
    total_games = len(list_of_runs)
    occurrence_percentage = (qualified_games / total_games) * 100
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage


def get_box_score_selected_team_F5(game_id, team_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)  # Adjusted to be one day prior to today
   # formatted_start_date = start_date.strftime("%m/%d/%Y")
   # formatted_end_date = end_date.strftime("%m/%d/%Y")
    formatted_start_date = "09/15/2023"
    formatted_end_date = "10/1/2023"
    game = statsapi.get("game", {"gamePk": game_id, "startDate": formatted_start_date, "endDate": formatted_end_date})
    linescore_data = game["liveData"]["linescore"]["innings"]
    first_5_innings = linescore_data[:5]

    runs_scored = sum(inning['home']['runs'] if game['gameData']['teams']['home']['id'] == team_id
                      else inning['away']['runs'] if game['gameData']['teams']['away']['id'] == team_id
    else 0
                      for inning in first_5_innings)

    return runs_scored


def calculate_team_total_run_occurrence_percentage_5_innings(list_of_runs, min_runs):
    qualified_games = sum(1 for runs in list_of_runs if runs >= min_runs)
    total_games = len(list_of_runs)
    occurrence_percentage = (qualified_games / total_games) * 100
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage
