from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import calendar
import discord
import bot_timing as bt
import bot_db as bd
import bot_response as br
import bot_permissions as bp

class InvalidTimeDurationStringError(Exception):
    pass

TIME_DURATION_RE = re.compile(r"\s*(\d*)\s*(mi|ho|da|we|mo|ye)\w*\s*")
#tuple of (time_interval_index, n (like in n_months_later))
def parse_time_duration_str(time_duration_str: str) -> tuple[int, int]:
    m = re.fullmatch(TIME_DURATION_RE, time_duration_str.lower())
    if m is None:
        raise InvalidTimeDurationStringError("Failed to parse time duration string.")
    n = int(m[1])
    time_interval_index = bt.TIME_INTERVAL_ABBREVIATIONS_INV[m[2]]
    return (time_interval_index, n)

class InvalidRepeatStringError(Exception):
    pass
class ZeroRepeatTimeError(Exception):
    pass

def parse_repeat_str(repeat_str: str) -> tuple[int, int]:
    try:
        time_interval_index, n = parse_time_duration_str(repeat_str)
        if n == 0:
            raise ZeroRepeatTimeError("Repeat time is 0.")
        return time_interval_index, n
    except InvalidTimeDurationStringError:
        raise InvalidRepeatStringError("Failed to parse repeat string.")

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

ABSOLUTE_TIME_RE = re.compile(
    r'\s*(?:(\d+)\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d\d\d\d)?)?\s*(\d?\d)\s*(?::\s*(\d\d))?\s*([ap]m)?\s*'
)
#returns tuple of (start_time, is_12_hr)
def parse_start_str(start_str: str, now: datetime) -> tuple[datetime, bool]:
    m = re.fullmatch(ABSOLUTE_TIME_RE, start_str.lower())
    if m is None:
        try:
            time_interval_index, n = parse_time_duration_str(start_str)
            return (bt.TIME_INTERVAL_FUNCTIONS[time_interval_index](now, n), False)
        except Exception:
            raise InvalidStartTimeStringError("Failed to parse start time string (format of start time given is invalid).")
    
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
            raise ZeroDayValueError("Start time day value is 0.")
        if day > days_in_month:
            raise TooLargeDayValueError(f"Start time day value is too large for that month (day value is {day} and highest allowed day value is {days_in_month}).")
        try:
            start = datetime(year, month, day, tzinfo=now.tzinfo)
        except:
            raise InvalidDateError("Date is invalid.")
    
    #read in time
    hour = int(hour_str)
    min = int(min_str) if min_str is not None else 0
    if min > 59:
        raise TooLargeMinuteValueError(f"Minute value is too large (minute value is {min} and highest allowed minute is 59).")
    is_12_hr = ampm_str is not None
    if is_12_hr:
        if hour == 0:
            raise ZeroHourValueError("Hour value is 0 in 12 hour time (lowest allowed hour value is 1).")
        if hour > 12:
            raise TooLarge12HourValueError(f"Hour value is too large for 12 hour time (hour value is {hour} and highest allowed hour value is 12).")

        am = ampm_str.lower()[0] == 'a'
        if am:
            if hour == 12:
                hour = 0
        else:
            if hour != 12:
                hour += 12
    else:
        if hour > 23:
            raise TooLarge24HourValueError("Hour value is too large for 24 hour time (hour value is {hour} and highest allowed hour value is 23).")
    
    start = start.replace(hour=hour, minute=min, second=0, microsecond=0)

    if start < now:
        if day_str is None: #so you can specify a time in the next day without an annoying error
            start += timedelta(days=1)
    if start < now:
        raise ValueError(f"Start is before the current time (current time is {bt.format_datetime(now, is_12_hr)} and start time is {bt.format_datetime(start, is_12_hr)}).")
    
    return (start, is_12_hr)

class ZeroLengthNameError(Exception):
    pass
class TooLongNameError(Exception):
    pass

def format_repeat(repeat_interval_index: int, n: int) -> str:
    if n != 1:
        return f"{n} {bt.TIME_INTERVAL_NAMES[repeat_interval_index]}s"
    else:
        return f"{bt.TIME_INTERVAL_NAMES[repeat_interval_index]}"

def format_local_and_UTC_time(time: datetime, is_12_hr: bool, user_has_tz: bool):
    return (f"**Time:** {bt.format_datetime(time, is_12_hr)} {"local time" if user_has_tz else "UTC"}" + 
            f"{f" ({bt.format_datetime(bt.to_utc(time), is_12_hr)} UTC)" if user_has_tz else ""}")

# tuple of (start_time, time_interval_index, n (like in n_months_later), name, response)
# expects string in the format start [datetime] name [name] repeat [repeat] (optional)
def parse_set_reminder(input: str, now: datetime, user_has_tz: bool, reply_message_id: int|None) -> tuple[datetime, int|None, int|None, str, br.Response]:
    start_time_arg = "time:"
    repeat_arg = "repeat:"

    start_time_index = input.find(start_time_arg)
    repeat_index = input.find(repeat_arg)

    name = ""
    start_time, is_12_hr = None, None
    repeat_interval_index = None
    n = None
    if start_time_index == -1 and repeat_index == -1:
        name = input.strip()
        start_time = now
        is_12_hr = False
    elif start_time_index == -1 and repeat_index != -1:
        name = input[:repeat_index].strip()
        start_time = now
        is_12_hr = False
        repeat_str = input[repeat_index + len(repeat_arg):].strip()
        repeat_interval_index, n = parse_repeat_str(repeat_str)
    elif start_time_index != -1 and repeat_index == -1:
        name = input[:start_time_index].strip()
        start_time_str = input[start_time_index + len(start_time_arg):]
        start_time, is_12_hr = parse_start_str(start_time_str, now)
    else:
        name = input[:min(start_time_index, repeat_index)].strip()
        start_time_str = None
        repeat_str = None
        if start_time_index < repeat_index:
            start_time_str = input[start_time_index + len(start_time_arg):repeat_index]
            repeat_str = input[repeat_index + len(repeat_arg):]
        else:
            start_time_str = input[start_time_index + len(start_time_arg):]
            repeat_str = input[repeat_index + len(repeat_arg):start_time_index]
        start_time, is_12_hr = parse_start_str(start_time_str, now)
        repeat_interval_index, n = parse_repeat_str(repeat_str)

    if len(name) == 0:
        raise ZeroLengthNameError("No name given.")
    if len(name) > 64:
        raise TooLongNameError(f"Name is too long (name length is {len(name)} characters and max length is 64 characters).")

    response = br.Response(
        title=f"Reminder `{name}` set{" with custom message" if reply_message_id is not None else ""}:",
        txt=f"**Time:** {format_local_and_UTC_time(start_time, is_12_hr, user_has_tz)}"
    )
    response.txt += "."
    if repeat_interval_index is not None: #has repeat
        response.txt += f"\n**Repeat:** Every {format_repeat(repeat_interval_index, n)}." # type: ignore n can't be null at this point

    if repeat_interval_index == 3 and start_time.day > 28: #month
        response.warnings.append(f"Reminder is set to repeat per month, but some months have less than {start_time.day} days." +
                              " On these months, the reminder will be shifted to the last day of the month.")
    
    if not user_has_tz:
        response.notes.append(f"You have not set your timezone, so UTC is assumed. Consider setting your timezone with" +
                              f" `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}`.")

    return (start_time, repeat_interval_index, n, name, response)

def set_reminder(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    if not user_perms >= bp.EDIT_REMINDERS:
        return bp.make_lacking_perms_response(f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]][0]}`",
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
            txt=str(e),
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[set_reminder]]]
        )
    
    try:
        bd.set_reminder(name, channel_id, reply_message_id, user_id, start_time, repeat_interval_index, repeat_interval_increment)
    except Exception as e:
        notes = [USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[set_reminder]]]
        if isinstance(e, bd.ReminderAlreadyExistsError):
            notes.append(f"Note: You can remove a reminder using `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_reminder]][0]}`.")

        return br.Response(
            is_error = True,
            title="Adding reminder failed:",
            txt=str(e),
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
        bd.remove_reminder(name, channel_id)
    except Exception as e:
        return br.Response(
            is_error = True,
            title="Removing reminder failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[remove_reminder]]]
        )
    
    return br.Response(
        title=f"Removed reminder `{name}`."
    )

def remove_all_reminders(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    if not user_perms >= bp.EDIT_REMINDERS:
        return bp.make_lacking_perms_response(f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_all_reminders]][0]}`",
                                              user_name,
                                              bp.EDIT_REMINDERS)
    
    try:
        bd.remove_all_reminders(channel_id)
    except Exception as e:
        return br.Response(
            is_error = True,
            title="Removing all reminders failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[remove_all_reminders]]]
        )
    
    return br.Response(
        title=f"Removed all reminders from this channel."
    )

def format_reminder(row: tuple[str, int, int|None, int, int, int, bool, int|None, int|None, int|None], user_tz: ZoneInfo) -> str:
    #i looooove f-strings
    return (f"`{row[0]}`: {bt.format_datetime(datetime.fromtimestamp(row[4], user_tz))}" +
            f"{(f" | Repeats every {format_repeat(row[7], row[8])}" # type: ignore (relevant row values can't be null at this point)
                f" | Next repeat: {bt.format_datetime(datetime.fromtimestamp(row[5], user_tz))}") if row[6] else ""}")

def list_reminders(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    reminders = bd.get_all_reminders(channel_id)
    if len(reminders) == 0:
        return br.Response(
            title="There are no reminders in this channel."
        )
    
    user_tz = bt.UTC
    try:
        user_tz_str = bd.get_user_timezone(user_id)
        user_tz = ZoneInfo(user_tz_str)
    except:
        pass

    reminder_strs = [format_reminder(r, user_tz) for r in reminders]
    return br.Response(
        title=f"There are {len(reminders)} reminders in this channel:",
        txt="\n".join(reminder_strs)
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
            title=f"Timezone for user `{user_name}` is {bd.get_user_timezone(user_id)}."
        )
    except Exception as e:
        return br.Response(
            is_error = True,
            title=f"Getting timezone for user `{user_name}` failed:",
            txt=f"{str(e)}.",
            notes=[USE_HELP_COMMAND_NOTES[COMMAND_FUNCTIONS_INV[get_timezone]],
                   f"Consider setting your timezone with {COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}"]
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

def current_time(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response:
    user_tz = bt.UTC
    user_has_tz = False
    try:
        user_tz_str = bd.get_user_timezone(user_id)
        user_tz = ZoneInfo(user_tz_str)
        user_has_tz = True
    except:
        pass

    return br.Response(
        title=f"Current time for user `{user_name}`:",
        txt=f"{format_local_and_UTC_time(datetime.now(user_tz), True, user_has_tz)}."
    )

def help(input: str, channel_id: int, user_id: int, user_name: str, user_perms: discord.Permissions, reply_message_id: int|None) -> br.Response|None:
    command_name = input.strip()
    if command_name == '':
        commands = [f"`{COMMAND_PREFIX}{COMMAND_NAMES[i][0]}`" for i in range(len(COMMAND_NAMES))]
        return br.Response(
            title="Help:",
            txt=f"All available commands: \n{"\n".join(commands)}\n\n" +
                f"To view detailed help for a command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]} [your command]`",
            warnings=[f"This bot is currently in early development. Things may change unexpectedly. Do not yet trust this bot for important reminders."]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]][0]}:",
            txt="This command adds a reminder to the current channel, with an optional custom message.\n\n" +
                "To use this command, use the format " +
                f"`{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]][0]} [name of reminder] time: [time of reminder] repeat: [repeat interval of reminder]`\n\n" +
                "Time can be specified as either absolute or relative. The format for absolute is `[dd] [month name] [yyyy] [hh::mm] [am/pm]`, " +
                "and the format for relative is `[integer number] [unit of time]`, where the unit of time can be minute, hour, day, week, month, or year.\n" +
                "The format for repeat is also `[integer number] [unit of time]`." +
                "Time and repeat are both optional arguments, and their formats are extremely flexible. " +
                "For example, most of the parts of the absolute time format can be omitted and inferred from the current time.\n\n" +
                f"To add a custom message to your reminder, send the custom message and then reply to it when sending `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]][0]}`.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_reminder]][1:])}`",
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
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_all_reminders]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_all_reminders]][0]}:",
            txt="This command removes all reminders from the current channel.\n\n" +
                f"To use this command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_all_reminders]][0]}`.",
            notes=[f"You must have the following permissions to use this command: {bp.make_permissions_list(bp.EDIT_REMINDERS)}."]
        )
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[list_reminders]][0]}:",
            txt="This command lists the names and details of all reminders in this channel.\n\n" +
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
    if command_name in COMMAND_NAMES[COMMAND_FUNCTIONS_INV[current_time]]:
        return br.Response(
            title=f"Help for {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[current_time]][0]}:",
            txt=f"This command gets your current time, according to the timezone set by `{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[set_timezone]][0]}`.\n\n" +
                f"To use this command, use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[current_time]][0]}`.\n\n" +
                f"Aliases of this command: `{", ".join(COMMAND_NAMES[COMMAND_FUNCTIONS_INV[current_time]][1:])}`",
            notes=[f"You can remove your timezone with {COMMAND_NAMES[COMMAND_FUNCTIONS_INV[remove_timezone]][0]}."]
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
    
    args_index = input.find(command_name) + len(command_name)
    command_args = input[args_index:]
    return COMMAND_FUNCTIONS[command_index](command_args, channel_id, user_id, user_name, user_perms, reply_message_id)

COMMAND_PREFIX = "!!"
COMMAND_NAMES = [ #1st is canonical name, rest are aliases
    ["set_reminder", "add_reminder", "remind", "sr", "ar"],
    ["remove_reminder", "delete_reminder", "rr", "dr"],
    ["remove_all_reminders"], #no aliases because you don't want to typo this
    ["list_reminders", "lr"],
    ["set_timezone", "set_tz", "st"],
    ["get_timezone", "get_tz", "gt"],
    ["remove_timezone", "delete_timezone", "remove_tz", "delete_tz", "rt", "dt"],
    ["current_time", "my_time", "time", "ct", "mt"],
    ["help"]
]
COMMAND_NAMES_INV = {c: i for i, cl in enumerate(COMMAND_NAMES) for c in cl}
COMMAND_FUNCTIONS = [
    set_reminder,
    remove_reminder,
    remove_all_reminders,
    list_reminders,
    set_timezone,
    get_timezone,
    remove_timezone,
    current_time,
    help,
]
COMMAND_FUNCTIONS_INV = {c: i for i, c in enumerate(COMMAND_FUNCTIONS)}

USE_HELP_NOTE = f"Use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]}` to see the list of available commands."
USE_HELP_COMMAND_NOTES = [f"Use `{COMMAND_PREFIX}{COMMAND_NAMES[COMMAND_FUNCTIONS_INV[help]][0]} {COMMAND_NAMES[i][0]}` to learn how to use {COMMAND_NAMES[i][0]}." 
                          for i in range(len(COMMAND_NAMES))]