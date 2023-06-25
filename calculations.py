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


def get_game_ids_last_n_days(team_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    formatted_end_date = end_date.strftime("%m/%d/%Y")
    last_n_days_games = statsapi.schedule(start_date=formatted_start_date, end_date=formatted_end_date, team=team_id)
    return [game['game_id'] for game in last_n_days_games]


def get_ml_results(game_id, num_days):
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=num_days)
    end_date = today - datetime.timedelta(days=1)  # Adjusted to be one day prior to today
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    formatted_end_date = end_date.strftime("%m/%d/%Y")
    game = statsapi.get("game", {"gamePk": game_id, "startDate": formatted_start_date, "endDate": formatted_end_date})
    linescore_data = game["liveData"]["linescore"]["innings"]
    first_5_innings = linescore_data[:5]

    runs_team_a = []
    runs_team_b = []

    for inning in first_5_innings:
        team_a_runs = inning['home']['runs']
        team_b_runs = inning['away']['runs']

        runs_team_a.append(team_a_runs)
        runs_team_b.append(team_b_runs)

    team_a_id = game['gameData']['teams']['home']['id']
    team_a_name = TEAM_NAMES.get(team_a_id, "Unknown Team")
    team_b_id = game['gameData']['teams']['away']['id']
    team_b_name = TEAM_NAMES.get(team_b_id, "Unknown Team")

    final_runs_team_a = sum(runs_team_a)
    final_runs_team_b = sum(runs_team_b)

    return {
        "Team_A": {
            "Runs": runs_team_a,
            "ID": team_a_id,
            "Name": team_a_name,
            "Total_Runs": final_runs_team_a
        },
        "Team_B": {
            "Runs": runs_team_b,
            "ID": team_b_id,
            "Name": team_b_name,
            "Total_Runs": final_runs_team_b
        }
    }


def calculate_win_percentage(results, team_id):
    total_games = 0
    team_wins = 0

    for game in results:
        team_a_id = game["Team_A"]["ID"]
        team_b_id = game["Team_B"]["ID"]
        team_a_runs = game["Team_A"]["Total_Runs"]
        team_b_runs = game["Team_B"]["Total_Runs"]

        if team_a_id == team_id:
            total_games += 1
            if team_a_runs > team_b_runs:
                team_wins += 1
        elif team_b_id == team_id:
            total_games += 1
            if team_b_runs > team_a_runs:
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
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    formatted_end_date = end_date.strftime("%m/%d/%Y")
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
    formatted_start_date = start_date.strftime("%m/%d/%Y")
    formatted_end_date = end_date.strftime("%m/%d/%Y")
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
