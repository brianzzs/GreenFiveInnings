import datetime

# Emergency offseason fallback:
# Pin schedule/stat lookups to the 2025 regular season until 2026 games exist.
FORCED_SEASON_YEAR = "2025"
SEASON_START_DATE = datetime.date(2025, 1, 1)
SEASON_REFERENCE_DATE = datetime.date(2025, 9, 28)  # Last 2025 regular season day


def standings_date_str() -> str:
    return SEASON_REFERENCE_DATE.strftime("%Y-%m-%d")
