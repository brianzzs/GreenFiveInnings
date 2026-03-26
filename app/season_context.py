import datetime
import os
from typing import Optional


def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    return datetime.datetime.strptime(value, "%Y-%m-%d").date()


def reference_date() -> datetime.date:
    """Return the effective date for schedule/standings queries.

    Defaults to today's date, but can be overridden for local debugging or
    offseason pinning with REFERENCE_DATE=YYYY-MM-DD.
    """
    return _parse_date(os.getenv("REFERENCE_DATE")) or datetime.date.today()


def active_season_year(ref_date: Optional[datetime.date] = None) -> str:
    """Return the active MLB season year.

    Defaults to the reference date's year, but can be pinned with
    FORCED_SEASON_YEAR for debugging/offseason support.
    """
    forced = os.getenv("FORCED_SEASON_YEAR")
    if forced:
        return forced
    return str((ref_date or reference_date()).year)


def standings_date_str() -> str:
    return reference_date().strftime("%Y-%m-%d")


def season_start_date(ref_date: Optional[datetime.date] = None) -> datetime.date:
    """Use January 1 of the active season as the broad search floor."""
    return datetime.date(int(active_season_year(ref_date)), 1, 1)
