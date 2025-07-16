from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import calendar
import bot_timing as bt
import bot_db as bd

class InvalidStartTimeStringError(Exception):
    pass
class ZeroDayValueError(Exception):
    pass
class TooLargeDayValueError(Exception):
    pass
class InvalidDateError(Exception):
    pass
class TooLargeMinuteValueError(Exception):
    pass
class ZeroHourValueError(Exception):
    pass
class TooLargeHourValueError(Exception):
    pass
class TooLarge12HourValueError(TooLargeHourValueError):
    pass
class TooLarge24HourValueError(TooLargeHourValueError):
    pass

START_RE = re.compile(
    r'\s*(?:(\d+)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d\d\d\d)?)?\s*(\d?\d)\s*:\s*(\d\d)\s*([ap]m)?\s*'
)
#returns tuple of (start_time, is_12_hr)
def parse_start_str(start_str: str, now: datetime) -> tuple[datetime, bool]:
    m = re.fullmatch(START_RE, start_str.lower())
    if m == None:
        raise InvalidStartTimeStringError("Failed to parse start time string (format of start time given is invalid)")
    
    day_str = m[1]
    month_abbr_str = m[2]
    year_str = m[3]
    hour_str = m[4]
    min_str = m[5]
    ampm_str = m[6]

    #read in date
    start = None
    if not day_str: #only time provided
        start = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    else:
        year = int(year_str) if year_str else now.year
        month = bt.MONTH_ABBRS_INV[month_abbr_str] + 1 #datetime expects 1-indexed
        day = int(day_str)
        _, days_in_month = calendar.monthrange(year, month)
        if day == 0:
            raise ZeroDayValueError("Start time day value is 0")
        if day > days_in_month:
            raise TooLargeDayValueError(f"Start time day value is too large for that month (day value is {day} and highest allowed day value is {days_in_month})")
        try:
            start = datetime(year, month, day, tzinfo=now.tzinfo)
        except:
            raise InvalidDateError("Date is invalid")
    
    #read in time
    hour = int(hour_str)
    min = int(min_str)
    if min > 59:
        raise TooLargeMinuteValueError(f"Minute value is too large (minute value is {min} and highest allowed minute is 59)")
    is_12_hr = ampm_str != None
    if is_12_hr:
        am = ampm_str.lower()[0] == 'a'
        if am:
            if hour == 0:
                raise ZeroHourValueError("Hour value is 0 in 12 hour time (lowest allowed hour value is 1)")
            if hour > 12:
                raise TooLarge12HourValueError(f"Hour value is too large for 12 hour time (hour value is {hour} and highest allowed hour value is 12)")

            if hour == 12:
                hour = 0
        else:
            if hour > 23:
                raise TooLarge24HourValueError("Hour value is too large for 24 hour time (hour value is {hour} and highest allowed hour value is 24)")

            if hour != 12:
                hour += 12
    
    start = start.replace(hour=hour, minute=min, second=0, microsecond=0)

    if start < now:
        if not day_str: #so you can specify a time in the next day without an annoying error
            start += timedelta(days=1)
        raise ValueError(f"Start is before the current time (current time is {bt.format_datetime(now, is_12_hr)} and start time is {bt.format_datetime(start, is_12_hr)})")
    
    return (start, is_12_hr)

class InvalidRepeatStringError(Exception):
    pass
class ZeroRepeatTimeError(Exception):
    pass

REPEAT_RE = re.compile(r"\s*(\d*)\s*([hdwmy])\w*\s*")
#tuple of (time_interval_index, n (like in n_months_later))
def parse_repeat_str(repeat_str: str) -> tuple[int, int]:
    m = re.fullmatch(REPEAT_RE, repeat_str.lower())
    if m == None:
        raise InvalidRepeatStringError("Failed to parse repeat string")
    n = int(m[1])
    if n == 0:
        raise ZeroRepeatTimeError("Repeat time is 0")
    time_interval_index = bt.TIME_INTERVAL_LETTERS_INV[m[2]]
    return (time_interval_index, n)

class NoNameParameterError(Exception):
    pass

# tuple of (start_time, time_interval_index, n (like in n_months_later), name, message)
# expects string in the format start [datetime] name [name] repeat [repeat] (optional)
def parse_set_reminder(input: str, now: datetime, user_has_tz: bool) -> tuple[datetime, int|None, int|None, str, str]:
    name_index = input.find("name:")
    if name_index == -1:
        raise NoNameParameterError("No name parameter given")

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
    start_time, is_12_hr = parse_start_str(start_str, now)
    name = name.strip()

    msg = f"Reminder set for {bt.format_datetime(start_time, is_12_hr)} local time"
    if start_time.tzinfo != bt.UTC:
        msg += f" ({bt.format_datetime(bt.to_utc(start_time), is_12_hr)} UTC)"
    if time_interval_index != None: #has repeat
        if n != 1:
            msg += f" and will repeat every {n} {bt.TIME_INTERVAL_NAMES[time_interval_index]}s."
        else:
            msg += f" and will repeat every {bt.TIME_INTERVAL_NAMES[time_interval_index]}."
    else:
        msg += "."

    if time_interval_index == 3 and start_time.day > 28: #month
        msg += f"\n\nNote: reminder is set to repeat per month, but some months have less than {start_time.day} days."
        msg += " On these months, the reminder will be shifted to the last day of the month."
    
    if not user_has_tz:
        msg += f"\n\nNote: you have not set your timezone, so UTC is assumed. If you want, set your timezone with {COMMAND_PREFIX}{COMMAND_NAMES[3]}."

    return (start_time, time_interval_index, n, name, msg)

def add_reminder(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    user_tz = bt.UTC
    user_has_tz = False
    try:
        user_tz_str = bd.get_user_timezone(user_id)
        user_tz = ZoneInfo(user_tz_str)
        user_has_tz = True
    except:
        pass

    now = datetime.now(user_tz)

    start_time, repeat_interval_index, repeat_interval_increment, name, msg = None, None, None, None, None
    try:
        start_time, repeat_interval_index, repeat_interval_increment, name, msg = parse_set_reminder(input, now, user_has_tz)
    except Exception as e:
        return f"Parsing reminder failed! Error: {str(e)}."
    
    try:
        bd.add_reminder(name, channel_id, reply_message_id, user_id, start_time, repeat_interval_index, repeat_interval_increment)
    except Exception as e:
        msg = f"Adding reminder failed! Error: {str(e)}."
        if type(e) == bd.ReminderAlreadyExistsError:
            msg += f"\n\nNote: You can remove a reminder using {COMMAND_PREFIX}{COMMAND_NAMES[1]}."
        return msg
    
    return msg

def remove_reminder(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    name = input.strip()

    try:
        bd.remove_reminder(name, channel_id) #TODO: verify perms somewhere!!!
    except Exception as e:
        return f"Removing reminder failed! Error: {str(e)}."
    
    return f"Removed reminder '{name}'."

def list_reminders(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    reminders = bd.get_all_reminders(channel_id)
    if len(reminders) == 0:
        return "There are no reminders in this channel."
    
    names = [r[0] for r in reminders]
    return f"All reminders in this channel: {", ".join(names)}"

def set_timezone(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    tz_name = input.strip()

    try:
        ZoneInfo(tz_name)
    except Exception as e:
        return f"Setting timezone failed! Error: {tz_name} is not a valid timezone name."

    bd.set_user_timezone(user_id, tz_name)
    return f"Set timezone to {tz_name}."

def get_timezone(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    try:
        return f"User timezone is {bd.get_user_timezone(user_id)}"
    except Exception as e:
        return f"Getting timezone failed! Error: {str(e)}"

def remove_timezone(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str:
    try:
        bd.remove_user_timezone(user_id)
    except Exception as e:
        return f"Removing timezone failed! Error: {str(e)}."
    
    return f"User timezone removed."

def parse_command(input: str, channel_id: int, user_id: int, reply_message_id: int|None) -> str|None:
    if input[:2] != COMMAND_PREFIX:
        return 
    
    command_name = input[2:].split(maxsplit=1)[0]
    command_index = None
    try:
        command_index = COMMAND_NAMES_INV[command_name]
    except:
        return f"Command {command_name} does not exist."
    
    command_args = input[2+len(command_name):]
    return COMMAND_FUNCTIONS[command_index](command_args, channel_id, user_id, reply_message_id)

COMMAND_PREFIX = "!!"
COMMAND_NAMES = [
    "add_reminder",
    "remove_reminder",
    "list_reminders",
    "set_timezone",
    "get_timezone",
    "remove_timezone"
]
COMMAND_NAMES_INV = {c: i for i, c in enumerate(COMMAND_NAMES)}
COMMAND_FUNCTIONS = [
    add_reminder,
    remove_reminder,
    list_reminders,
    set_timezone,
    get_timezone,
    remove_timezone,
]