from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import calendar

import discord
import bot_timing as bt
import bot_db as bd
import bot_response as br
import bot_permissions as bp

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
    r'\s*(?:(\d+)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d\d\d\d)?)?\s*(\d?\d)\s*(?::\s*(\d\d))?\s*([ap]m)?\s*'
)
#returns tuple of (start_time, is_12_hr)
def parse_start_str(start_str: str, now: datetime) -> tuple[datetime, bool]:
    m = re.fullmatch(START_RE, start_str.lower())
    if m is None:
        raise InvalidStartTimeStringError("Failed to parse start time string (format of start time given is invalid)")
    
    day_str = m[1]
    month_abbr_str = m[2]
    year_str = m[3]
    hour_str = m[4]
    min_str = m[5]
    ampm_str = m[6]

    #read in date
    start = None
    if day_str is None: #only time provided
        start = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    else:
        year = int(year_str) if year_str is not None else now.year
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
    min = int(min_str) if min_str is not None else 0
    if min > 59:
        raise TooLargeMinuteValueError(f"Minute value is too large (minute value is {min} and highest allowed minute is 59)")
    is_12_hr = ampm_str is not None
    if is_12_hr:
        if hour == 0:
            raise ZeroHourValueError("Hour value is 0 in 12 hour time (lowest allowed hour value is 1)")
        if hour > 12:
            raise TooLarge12HourValueError(f"Hour value is too large for 12 hour time (hour value is {hour} and highest allowed hour value is 12)")

        am = ampm_str.lower()[0] == 'a'
        if am:
            if hour == 12:
                hour = 0
        else:
            if hour != 12:
                hour += 12
    else:
        if hour > 23:
            raise TooLarge24HourValueError("Hour value is too large for 24 hour time (hour value is {hour} and highest allowed hour value is 23)")
    
    start = start.replace(hour=hour, minute=min, second=0, microsecond=0)

    if start < now:
        if day_str is None: #so you can specify a time in the next day without an annoying error
            start += timedelta(days=1)
        raise ValueError(f"Start is before the current time (current time is {bt.format_datetime(now, is_12_hr)} and start time is {bt.format_datetime(start, is_12_hr)})")
    
    return (start, is_12_hr)

class InvalidRepeatStringError(Exception):
    pass
class ZeroRepeatTimeError(Exception):
    pass

REPEAT_RE = re.compile(r"\s*(\d*)\s*(mi|ho|da|we|mo|ye)\w*\s*")
#tuple of (time_interval_index, n (like in n_months_later))
def parse_repeat_str(repeat_str: str) -> tuple[int, int]:
    m = re.fullmatch(REPEAT_RE, repeat_str.lower())
    if m is None:
        raise InvalidRepeatStringError("Failed to parse repeat string")
    n = int(m[1])
    if n == 0:
        raise ZeroRepeatTimeError("Repeat time is 0")
    time_interval_index = bt.TIME_INTERVAL_ABBREVIATIONS_INV[m[2]]
    return (time_interval_index, n)

class NoTimeParameterError(Exception):
    pass

# tuple of (start_time, time_interval_index, n (like in n_months_later), name, response)
# expects string in the format start [datetime] name [name] repeat [repeat] (optional)
def parse_set_reminder(input: str, now: datetime, user_has_tz: bool, reply_message_id: int|None) -> tuple[datetime, int|None, int|None, str, br.Response]:
    start_time_arg = "time:"
    repeat_arg = "repeat:"

    start_time_index = input.find(start_time_arg)
    if start_time_index == -1:
        raise NoTimeParameterError("No start time given")

    name = ""
    repeat_index = input.find(repeat_arg)
    start_time_str = ""
    repeat_interval_index = None
    n = None
    if repeat_index == -1:
        start_time_str = input[start_time_index + len(start_time_arg):]
        name = input[:start_time_index].strip()
    else:
        repeat_str = ""
        if start_time_index < repeat_index:
            start_time_str = input[start_time_index + len(start_time_arg):repeat_index]
            repeat_str = input[repeat_index + len(repeat_arg):]
        else:
            start_time_str = input[start_time_index + len(start_time_arg):]
            repeat_str = input[repeat_index + len(repeat_arg):start_time_index]
        repeat_interval_index, n = parse_repeat_str(repeat_str)
        name = input[:min(start_time_index, repeat_index)].strip()
    start_time, is_12_hr = parse_start_str(start_time_str, now)

    response = br.Response(
        title=f"Reminder '{name}' set{" with custom message" if reply_message_id is not None else ""}:",
        txt=f"**Time:** {bt.format_datetime(start_time, is_12_hr)} {"local time" if user_has_tz else "UTC"}"
    )
    if start_time.tzinfo != bt.UTC:
        response.txt += f" ({bt.format_datetime(bt.to_utc(start_time), is_12_hr)} UTC)"
    response.txt += "."
    if repeat_interval_index is not None: #has repeat
        if n != 1:
            response.txt += f"\n**Repeat:** Every {n} {bt.TIME_INTERVAL_NAMES[repeat_interval_index]}s."
        else:
            response.txt += f"\n**Repeat:** Every {bt.TIME_INTERVAL_NAMES[repeat_interval_index]}."

    if repeat_interval_index == 3 and start_time.day > 28: #month
        response.warnings.append(f"Reminder is set to repeat per month, but some months have less than {start_time.day} days." +
                              " On these months, the reminder will be shifted to the last day of the month.")
    
    if not user_has_tz:
        response.notes.append(f"You have not set your timezone, so UTC is assumed. Consider setting your timezone with" +
                              f" `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}`.")

    return (start_time, repeat_interval_index, n, name, response)

def add_reminder(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    if not user_perms >= bp.EDIT_REMINDERS:
        return bp.make_lacking_perms_response(f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[add_reminder]][0]}`",
                                              user_name,
                                              bp.EDIT_REMINDERS)

    user_tz = bt.UTC
    user_has_tz = False
    try:
        user_tz_str = bd.get_user_timezone(user_id)
        user_tz = ZoneInfo(user_tz_str)
        user_has_tz = True
    except:
        pass

    now = datetime.now(user_tz)

    start_time, repeat_interval_index, repeat_interval_increment, name, response = None, None, None, None, None
    try:
        start_time, repeat_interval_index, repeat_interval_increment, name, response = parse_set_reminder(input, now, user_has_tz, reply_message_id)
    except Exception as e:
        return br.Response(
            is_error = True,
            title="Parsing reminder failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[add_reminder]]]
        )
    
    try:
        bd.add_reminder(name, channel_id, reply_message_id, user_id, start_time, repeat_interval_index, repeat_interval_increment)
    except Exception as e:
        notes = [USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[add_reminder]]]
        if isinstance(e, bd.ReminderAlreadyExistsError):
            notes.append(f"Note: You can remove a reminder using `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]}`.")

        return br.Response(
            is_error = True,
            title="Adding reminder failed:",
            txt=f"{str(e)}.",
            notes=notes
        )
    
    return response

def remove_reminder(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    if not user_perms >= bp.EDIT_REMINDERS:
        return bp.make_lacking_perms_response(f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]}`",
                                              user_name,
                                              bp.EDIT_REMINDERS)
    
    name = input.strip()

    try:
        bd.remove_reminder(name, channel_id) #TODO: verify perms somewhere!!!
    except Exception as e:
        return br.Response(
            is_error = True,
            title="Removing reminder failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[remove_reminder]]]
        )
    
    return br.Response(
        title=f"Removed reminder '{name}'."
    )

def list_reminders(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    reminders = bd.get_all_reminders(channel_id)
    if len(reminders) == 0:
        return br.Response(
            title="There are no reminders in this channel."
        )
    
    names = [r[0] for r in reminders]
    return br.Response(
        title="All reminders in this channel:",
        txt=", ".join(names)
    )

def set_timezone(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    tz_name = input.strip()

    try:
        ZoneInfo(tz_name)
    except:
        return br.Response(
            is_error = True,
            title=f"Setting timezone for user `{user_name}` failed:",
            txt=f"{tz_name} is not a valid timezone name.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[set_timezone]]]
        )

    bd.set_user_timezone(user_id, tz_name)
    return br.Response(
        title=f"Set timezone for user `{user_name}` to {tz_name}."
    )

def get_timezone(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    try:
        return br.Response(
            title=f"User timezone is {bd.get_user_timezone(user_id)}."
        )
    except Exception as e:
        return br.Response(
            is_error = True,
            title=f"Getting timezone for user `{user_name}` failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[get_timezone]]]
        )

def remove_timezone(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    try:
        bd.remove_user_timezone(user_id)
    except Exception as e:
        return br.Response(
            is_error=True,
            title=f"Removing timezone for user `{user_name}` failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[remove_timezone]]]
        )
    
    return br.Response(title=f"Timezone for user `{user_name}` removed.")

def help(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response|None:
    command_name = input.strip()
    if command_name == '':
        commands = [f"`{COMMAND_PREFIX}{COMMAND_NAMES[i][0]}`" for i in range(len(COMMAND_NAMES))]
        return br.Response(
            title="Help:",
            txt=f"All available commands: \n{"\n".join(commands)}\n\n" +
                f"To view detailed help for a command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]} [your command]`"
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[add_reminder]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[add_reminder]][0]}:",
            txt="This command adds a reminder to the current channel.\n\n" +
                "To use this command, use the format " +
                f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[add_reminder]][0]} [name of reminder] time: [time of reminder] repeat: [repeat interval of reminder]`\n\n" +
                "The format for time is `[dd] [month name] [yyyy] [hh::mm] [am/pm]`. This format is very flexible: " +
                "year can be omitted (or date can be omitted altogether), am/pm can be omitted to use 24 hour time, and month names can be abbreviated.\n\n"
                "Repeat is optional. If specified, it is in the format `[integer number] [unit of time]`, where the unit of time can be minute, hour, day, week, month, or year. " +
                "This format is also flexible: the unit of time can be abbreviated down to its first 2 letters.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[add_reminder]][1:])}`",
            notes=[f"You must have the following permissions to use this command: {bp.make_permissions_list(bp.EDIT_REMINDERS)}",
                   f"You can remove a reminder with `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]}`"]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]}:",
            txt="This command removes a reminder from the current channel.\n\n" +
                "To use this command, use the format " +
                f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]} [name of reminder].`\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][1:])}`",
            notes=[f"You must have the following permissions to use this command: {bp.make_permissions_list(bp.EDIT_REMINDERS)}."]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]][0]}:",
            txt="This command lists the names of all reminders in this channel.\n\n" +
                f"To use this command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]][0]}`.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]][1:])}`",
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}:",
            txt="This command sets your timezone, which will be used for all future reminders you add.\n\n"
                "To use this command, use the format " +
                f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]} [TZ identifier].` " +
                "You can find your TZ identifier [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#Time_zone_abbreviations).\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][1:])}`",
            notes=[f"You can get your current timezone with `{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[get_timezone]][0]}` " +
                   f"and remove your timezone with `{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][0]}`."]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[get_timezone]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[get_timezone]][0]}:",
            txt=f"This command gets your timezone, as set by `{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}`.\n\n" +
                f"To use this command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[get_timezone]][0]}`.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[get_timezone]][1:])}`",
            notes=[f"You can remove your timezone with {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][0]}."]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][0]}:",
            txt=f"This command removes your timezone, as set by `{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}`.\n\n" +
                f"To use this command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][0]}`.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][1:])}`"
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]}:",
            txt="This is the help command."
        )
    return br.Response(
        is_error=True,
        title=f"Help failed: Command {command_name} does not exist.",
        notes=[USE_HELP_NOTE]
    )

def parse_command(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response|None:
    if input[:len(COMMAND_PREFIX)] != COMMAND_PREFIX:
        return 
    
    command_name = input[len(COMMAND_PREFIX):].split(maxsplit=1)[0]
    command_index = None
    try:
        command_index = COMMAND_NAMES_INV[command_name]
    except:
        return br.Response(
            is_error=True,
            title=f"Command {command_name} does not exist.",
            notes=[USE_HELP_NOTE]
        )
    
    command_args = input[len(COMMAND_PREFIX)+len(command_name):]
    return COMMAND_FUNCTIONS[command_index](command_args, channel_id, user_id, user_name, user_perms, reply_message_id)

COMMAND_PREFIX = "!!"
COMMAND_NAMES = [ #1st is canonical name, rest are aliases
    ["add_reminder", "set_reminder", "remind", "ar"],
    ["remove_reminder", "delete_reminder", "rr"],
    ["list_reminders", "lr"],
    ["set_timezone", "set_tz", "st"],
    ["get_timezone", "get_tz", "gt"],
    ["remove_timezone", "delete_timezone", "remove_tz", "delete_tz", "rt"],
    ["help"]
]
COMMAND_NAMES_INV = {c: i for i, cl in enumerate(COMMAND_NAMES) for c in cl}
COMMAND_FUNCTIONS = [
    add_reminder,
    remove_reminder,
    list_reminders,
    set_timezone,
    get_timezone,
    remove_timezone,
    help,
]
COMMAND_FUNCTIONS_INV = {c: i for i, c in enumerate(COMMAND_FUNCTIONS)}

USE_HELP_NOTE = f"Use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]}` to see the list of available commands."
USE_HELP_COMMAND_NOTES = [f"Use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]} {COMMAND_NAMES[i][0]}` to learn how to use {COMMAND_NAMES[i][0]}." 
                          for i in range(len(COMMAND_NAMES))]