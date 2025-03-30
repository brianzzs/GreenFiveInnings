# Utility functions for pure calculations
from typing import List, Dict

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

def calculate_win_percentage(results: List[Dict], team_id: int) -> float:
    """Calculates the win percentage for a team based on a list of game results (F5 innings)."""
    if not results:
        return 0.0

    wins = 0
    valid_games = 0
    for game in results:
        # Check for necessary keys to avoid errors
        if not game or 'home_team' not in game or 'away_team' not in game or \
           'total_runs' not in game['home_team'] or 'total_runs' not in game['away_team'] or \
           'id' not in game['home_team'] or 'id' not in game['away_team']:
            continue 

        valid_games += 1
        home_runs = game['home_team']['total_runs']
        away_runs = game['away_team']['total_runs']
        is_home_team = game['home_team']['id'] == team_id
        is_away_team = game['away_team']['id'] == team_id

        if is_home_team and home_runs > away_runs:
            wins += 1
        elif is_away_team and away_runs > home_runs:
            wins += 1

    return (wins / valid_games * 100) if valid_games > 0 else 0.0


def calculate_nrfi_occurrence(first_inning_runs_list: List[tuple]) -> float:
    """Calculates the NRFI% based on a list of (home_runs, away_runs) tuples for the 1st inning."""
    if not first_inning_runs_list:
        return 0.0
    
    nrfi_games = sum(1 for home_runs, away_runs in first_inning_runs_list if home_runs == 0 and away_runs == 0)
    total_games = len(first_inning_runs_list)
    
    occurrence_percentage = (nrfi_games / total_games) * 100 if total_games > 0 else 0.0
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage


def calculate_team_total_run_occurrence_percentage_5_innings(list_of_runs: List[int], min_runs: float) -> float:
    """Calculates the percentage of games where a team scored >= min_runs in the first 5 innings."""
    if not list_of_runs:
        return 0.0
        
    qualified_games = sum(1 for runs in list_of_runs if runs >= min_runs)
    total_games = len(list_of_runs)
    
    occurrence_percentage = (qualified_games / total_games) * 100 if total_games > 0 else 0.0
    rounded_percentage = round(occurrence_percentage, 2)
    return rounded_percentage 