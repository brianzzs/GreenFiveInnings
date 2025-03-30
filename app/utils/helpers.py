import datetime
import pytz

def convert_utc_to_local(utc_datetime_str: str, target_tz: str = 'America/New_York') -> str:
    """Converts a UTC datetime string to a specified timezone."""
    try:
        utc_dt = datetime.datetime.strptime(utc_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
        utc_dt = pytz.UTC.localize(utc_dt)
        local_tz_obj = pytz.timezone(target_tz)
        local_dt = utc_dt.astimezone(local_tz_obj)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z%z") # Include timezone info
    except (ValueError, TypeError) as e:
        print(f"Error converting UTC time '{utc_datetime_str}': {e}")
        return utc_datetime_str 
    except pytz.UnknownTimeZoneError:
        print(f"Unknown timezone: {target_tz}. Falling back to UTC.")
        return utc_dt.strftime("%Y-%m-%d %H:%M:%S %Z%z") 