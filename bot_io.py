from datetime import datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo

import calendar

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
    return dt.astimezone(timezone.utc)

def format_datetime(dt: datetime, is_12_hr: bool = False) -> str:
    specifier = f"%A, %d %B %Y, {"%I:%M %p" if is_12_hr else "%H:%M"}"
    return dt.strftime(specifier)

def next_occurrence(now: datetime, year: int|None, month: int|None, day: int|None, hour: int, minute: int, second: int) -> datetime:
    assert 0 <= hour < 24
    assert 0 <= minute < 60
    assert 0 <= second < 60
    assert (not year and not month and not day) or (not year and month and day) or (year and month and day)

    target = datetime(year if year else now.year,
                      month if month else now.month,
                      day if day else now.day,
                      hour, minute, second, 0, now.tzinfo)

    if target < now:
        if year and month and day:
            raise ValueError("The specified time is before now.")
        if not year and month and day:
            target = datetime(now.year + 1, month, day,
                              hour, minute, second, 0, now.tzinfo)
        if not year and not month and not day:
            target += timedelta(days=1)

    return target

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
def first_positive_integer_str(s: str) -> str:
    """
    Return the first positive integer found in the string.
    Raise ValueError if:
      - the first numeric token is negative (e.g., '-5')
      - zero ('0')
      - a decimal number (e.g., '3.14')
      - there is more than one numeric token (integer or decimal) in the string
    """
    # Pattern matching optional sign, digits, and optional decimal part
    token_re = re.compile(r'[-+]?\d+(\.\d+)?')
    tokens = token_re.findall(s)  # returns list of tuples: group(0) is full match via finditer below
    
    # Let's get full matches with finditer to catch actual tokens
    matches = [m.group(0) for m in token_re.finditer(s)]
    
    if not matches:
        raise ValueError("No integer found")
    
    first = matches[0]
    
    # Validate the first token
    if re.fullmatch(r'-\d+', first):
        raise ValueError(f"Found negative number '{first}'")
    if re.fullmatch(r'\+?0+', first):
        raise ValueError(f"Found zero '{first}'")
    if re.fullmatch(r'[-+]?\d+\.\d+', first):
        raise ValueError(f"Found decimal number '{first}'")
    
    # If there's more than one numeric token, error
    if len(matches) > 1:
        raise ValueError(f"Found more than one number: {matches}")
    
    # It's a valid positive integer; strip any leading '+'
    return first.lstrip('+')

# TIME_RE = re.compile(
#     r'(\d+)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d\d(?:\d\d)?)\s*(\d\d)\s*:\s*(\d\d)\s*([ap]m)?'
# )
# def first_single_time(s: str) -> time:
#     """
#     Parse a single time in H:MM or HH:MM format from the string.
    
#     Returns:
#         datetime.time object.
    
#     Raises:
#         ValueError if:
#           - No valid time is found
#           - More than one valid time is found
#           - Specified time is invalid
#     """
#     matches = TIME_RE.findall(s)
#     if not matches:
#         raise ValueError("No time found in string")
#     if len(matches) > 1:
#         raise ValueError("Multiple times found")
    
#     hh_str, mm_str, ampm = matches[0]
#     hh, mm = int(hh_str), int(mm_str)
    
#     # Adjust hour based on AM/PM
#     if ampm:
#         if hh > 12:
#             raise ValueError("Invalid time found (hour value greater than 12)")
        
#         am = ampm.lower() == 'am'
#         if am:
#             if hh == 12:
#                 hh = 0
#         else:  # PM
#             if hh != 12:
#                 hh += 12
    
#     return time(hh, mm)

START_RE = re.compile(
    r'\s*(?:(\d+)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d\d\d\d)?)?\s*(\d?\d)\s*:\s*(\d\d)\s*([ap]m)?\s*'
)
def parse_start_str(start_str: str, now: datetime) -> datetime:
    m = re.fullmatch(START_RE, start_str.lower())
    if m == None:
        raise ValueError("Failed to parse start string")
    
    day_str = m[1]
    month_abbr_str = m[2]
    year_str = m[3]
    hour_str = m[4]
    min_str = m[5]
    ampm_str = m[6]

    print(day_str, month_abbr_str, year_str, hour_str, min_str, ampm_str)

    #read in date
    start = None
    if not day_str: #only time provided
        start = datetime(now.year, now.month, now.day)
    else:
        year = int(year_str) if year_str else now.year
        month = MONTH_ABBRS_INV[month_abbr_str] + 1 #datetime expects 1-indexed
        day = int(day_str)
        _, days_in_month = calendar.monthrange(year, month)
        if day == 0:
            raise ValueError("Day value is 0")
        if day > days_in_month:
            raise ValueError("Day value is too large for that month")
        try:
            start = datetime(year, month, day)
        except:
            raise ValueError("Date is invalid")
    
    #read in time
    hour = int(hour_str)
    min = int(min_str)
    if min > 59:
        raise ValueError("Minute value is too large")
    if ampm_str:
        am = ampm_str.lower()[0] == 'a'
        if am:
            if hour == 0:
                raise ValueError("Hour value is 0 in 12 hour time")
            if hour > 12:
                raise ValueError("Hour value is too large for 12 hour time")

            if hour == 12:
                hour = 0
        else:
            if hour > 23:
                raise ValueError("Hour value is too large for 24 hour time")

            if hour != 12:
                hour += 12
    
    start = start.replace(hour=hour, minute=min, second=0, microsecond=0)

    if start < now:
        raise ValueError("Start is before the current time")
    
    return start


REPEAT_RE = re.compile(r"\s*(\d*)\s*([hdwmy])\w*\s*")
#tuple of (time_interval_index, n (like in n_months_later))
def parse_repeat_str(repeat_str: str) -> tuple[int, int]:
    m = re.fullmatch(REPEAT_RE, repeat_str.lower())
    if m == None:
        raise ValueError("Failed to parse repeat string")
    n = int(m[1])
    if n == 0:
        raise ValueError("Repeat time cannot be 0")
    time_interval_index = TIME_INTERVAL_LETTERS_INV[m[2]]
    return (time_interval_index, n)

# tuple of (start_time, time_interval_index, n (like in n_months_later), name, message)
# expects string in the format start [datetime] name [name] repeat [repeat] (optional)
def parse_set_reminder(input: str, now: datetime) -> tuple[datetime, int|None, int|None, str, str]:
    name_index = input.find("name:")
    if name_index == -1:
        raise ValueError("No name parameter given! Type \"!help set_reminder\" for usage of this command")

    name = ""
    repeat_index = input.find("repeat:")
    start_str = ""
    time_interval_index = None
    n = None
    if repeat_index == -1:
        name = input[name_index + 5:]
    else:
        repeat_str = ""
        if name_index < repeat_index:
            name = input[name_index + 5:repeat_index]
            repeat_str = input[repeat_index + 7:]
        else:
            name = input[name_index + 5:]
            repeat_str = input[repeat_index + 7:name_index]
        time_interval_index, n = parse_repeat_str(repeat_str)
    start_str = input[:min(name_index, repeat_index) if repeat_index != -1 else name_index]
    print(start_str)
    start_time = parse_start_str(start_str, now)
    name = name.strip()

    return (start_time, time_interval_index, n, name, "")


#     n = None
#     time_interval_index = None

