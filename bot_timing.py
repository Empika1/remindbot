from datetime import datetime, timedelta, timezone
import calendar
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")

# Create mappings for full and short names
FULL = {name.lower(): idx for idx, name in enumerate(calendar.day_name)}
ABBR = {name.lower(): idx for idx, name in enumerate(calendar.day_abbr)}
def weekday_to_int(name: str) -> int | None:
    """
    Convert weekday name or abbreviation to integer.
    Returns None if the name isn't recognized.
    """
    n = name.lower()
    if n in FULL:
        return FULL[n]
    if n in ABBR:
        return ABBR[n]
    return None

def to_utc(dt: datetime):
    return dt.astimezone(UTC)

def format_datetime(dt: datetime, is_12_hr: bool = False) -> str:
    specifier = f"%A, %d %B %Y, {"%I:%M %p" if is_12_hr else "%H:%M"}"
    return dt.strftime(specifier)

def n_hours_later(now: datetime, n: int) -> datetime:
    return now + timedelta(hours=n)

def n_days_later(now: datetime, n: int) -> datetime:
    return now + timedelta(days=n)

def n_weeks_later(now: datetime, n: int) -> datetime:
    return now + timedelta(weeks=n)

#tuple of (datetime, warning). warning is when not all months have the day trying to be repeated
# #if the month selected doesn't have the day needed, it is instead rounded to the last day of the month
def n_months_later(now: datetime, n: int) -> tuple[datetime, str|None]:
    warning = None

    new_month = (now.month - 1 + n) % 12 + 1
    new_year = (now.month - 1 + n) // 12 + now.year
    _, days_in_month = calendar.monthrange(new_year, new_month)
    
    new_day = now.day
    if now.day > days_in_month:
        new_day = days_in_month
        warning = "Reminder clamped to the last day of the month."
    
    return (now.replace(year=new_year, month=new_month, day=new_day), warning)

def n_years_later(now: datetime, n: int) -> datetime:
    return now.replace(year=now.year + n)

TIME_INTERVAL_FUNCTIONS = [n_hours_later, n_days_later, n_weeks_later, n_months_later, n_years_later]
TIME_INTERVAL_NAMES = ["hour", "day", "week", "month", "year"]
TIME_INTERVAL_LETTERS = ["h", "d", "w", "m", "y"]
TIME_INTERVAL_LETTERS_INV = {c: i for i, c in enumerate(TIME_INTERVAL_LETTERS)}

MONTH_ABBRS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH_ABBRS_INV = {c: i for i, c in enumerate(MONTH_ABBRS)}