from datetime import datetime
import sqlite3
from zoneinfo import ZoneInfo
import bot_timing as bt

conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS reminders (
    name TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    reply_message_id INTEGER,
    setter_user_id INTEGER NOT NULL,
    start_timestamp INTEGER NOT NULL,
    next_timestamp INTEGER NOT NULL,
    has_repeat BOOLEAN NOT NULL,
    repeat_interval_index INTEGER,
    repeat_interval_increment INTEGER,
    repeat_increment_count INTEGER,
    PRIMARY KEY (name, channel_id),
    CHECK (NOT has_repeat OR repeat_interval_index IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_interval_increment IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_interval_increment > 0),
    CHECK (NOT has_repeat OR repeat_increment_count IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_increment_count >= 0)
);
               
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL
);
""")

class ReminderAlreadyExistsError(Exception):
    pass

def set_reminder(name: str, channel_id: int, reply_message_id: int|None, user_id: int,
                 start_time: datetime, repeat_interval_index: int|None, repeat_interval_increment: int|None):
    cursor.execute("""
        SELECT 1 FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    
    if cursor.fetchone() is not None:
        raise ReminderAlreadyExistsError(f"Reminder with name '{name}' already exists in this channel")

    start_timestamp = start_time.timestamp()
    cursor.execute("""
    INSERT INTO reminders (name, channel_id, reply_message_id, setter_user_id, start_timestamp, next_timestamp,
                           has_repeat, repeat_interval_index, repeat_interval_increment, repeat_increment_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (name, 
      channel_id,
      reply_message_id,
      user_id,
      start_timestamp,
      start_timestamp,
      repeat_interval_index != None,
      repeat_interval_index,
      repeat_interval_increment,
      0))
    conn.commit()

class ReminderDoesntExistError(Exception):
    pass

def remove_reminder(name: str, channel_id: int):
    # Check if the reminder exists and get the setter's user ID
    cursor.execute("""
        SELECT setter_user_id FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    
    row = cursor.fetchone()
    if row is None:
        raise ReminderDoesntExistError(f"Reminder with name '{name}' doesn't exist in this channel")

    # Perform the deletion
    cursor.execute("""
        DELETE FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    conn.commit()

def remove_all_reminders(channel_id: int):
    cursor.execute("""
        DELETE FROM reminders WHERE channel_id = ?
    """, (channel_id,))
    conn.commit()

def get_all_reminders(channel_id: int) -> list[tuple[str, int, int|None, int, int, int, bool, int|None, int|None, int|None]]:
    cursor.execute("""
        SELECT name, channel_id, reply_message_id, setter_user_id, start_timestamp, next_timestamp,
            has_repeat, repeat_interval_index, repeat_interval_increment, repeat_increment_count 
        FROM reminders 
        WHERE channel_id = ?
    """, (channel_id,))
    return cursor.fetchall()

def set_user_timezone(user_id: int, timezone: str):
    cursor.execute("""
    INSERT OR REPLACE INTO users (id, timezone)
    VALUES (?, ?)
""", (user_id, timezone))
    conn.commit()

class UserNotInDatabaseError(Exception):
    pass

def get_user_timezone(user_id: int) -> str:
    cursor.execute("SELECT timezone FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if row is not None:
        return row[0]
    else:
        raise UserNotInDatabaseError("User doesn't have a set timezone")

class TimezoneDoesntExistError(Exception):
    pass

def remove_user_timezone(user_id: int):
    # Check if the reminder exists and get the setter's user ID
    cursor.execute("""
        SELECT timezone FROM users WHERE id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if row is None:
        raise UserNotInDatabaseError("User doesn't have a set timezone")

    # Perform the deletion
    cursor.execute("""
        DELETE FROM users WHERE id = ?
    """, (user_id,))
    conn.commit()


def get_due_reminders(now: datetime) -> list[tuple[str, int, int|None, int, int, int, bool, int|None, int|None, int|None]]:
    cursor.execute("""
        SELECT name, channel_id, reply_message_id, setter_user_id, start_timestamp, next_timestamp,
               has_repeat, repeat_interval_index, repeat_interval_increment, repeat_increment_count 
        FROM reminders 
        WHERE next_timestamp <= ?
    """, (now.timestamp(),))
    return cursor.fetchall()

# def update_reminders(now: datetime):
#     now_timestamp = now.timestamp()
#     cursor.execute("""
#         DELETE FROM reminders WHERE next_timestamp <= ? AND NOT has_repeat
#     """, (now_timestamp,))
#     conn.commit()

#     cursor.execute("""
#         SELECT name, channel_id, setter_user_id, start_timestamp, 
#                repeat_interval_index, repeat_interval_increment, repeat_increment_count
#         FROM reminders 
#         WHERE next_timestamp <= ? AND has_repeat
#     """, (now_timestamp,))
#     repeating_reminders = cursor.fetchall()

#     for (name, channel_id, setter_user_id, start_timestamp, 
#          repeat_interval_index, repeat_interval_increment, repeat_increment_count) in repeating_reminders:
#         new_repeat_interval_count = repeat_increment_count + 1

#         cursor.execute("""
#             SELECT timezone FROM users WHERE id = ?
#         """, (setter_user_id,))
#         timezone_row = cursor.fetchone()
#         timezone_string = timezone_row[0] if timezone_row is not None else 'UTC'
#         timezone = ZoneInfo(timezone_string)

#         start_time = datetime.fromtimestamp(start_timestamp, timezone)
#         next_time = bt.TIME_INTERVAL_FUNCTIONS[repeat_interval_index](start_time, repeat_interval_increment * new_repeat_interval_count)

#         cursor.execute("""
#             UPDATE reminders
#             SET next_timestamp = ?, repeat_increment_count = ?
#             WHERE name = ? AND channel_id = ?;
#         """, (next_time.timestamp(), new_repeat_interval_count, name, channel_id))
#         conn.commit()

def update_reminder(name: str, channel_id: int, now: datetime):
    now_timestamp = now.timestamp()

    cursor.execute("""
        SELECT name, channel_id, setter_user_id, start_timestamp, 
               repeat_interval_index, repeat_interval_increment, repeat_increment_count
        FROM reminders 
        WHERE name == ? AND channel_id == ? AND next_timestamp <= ? AND has_repeat
    """, (name, channel_id, now_timestamp))
    repeating_reminder = cursor.fetchone()

    if repeating_reminder is not None:
        (name, channel_id, setter_user_id, start_timestamp, 
            repeat_interval_index, repeat_interval_increment, repeat_increment_count) = repeating_reminder
        new_repeat_interval_count = repeat_increment_count + 1

        cursor.execute("""
            SELECT timezone FROM users WHERE id = ?
        """, (setter_user_id,))
        timezone_row = cursor.fetchone()
        timezone_string = timezone_row[0] if timezone_row is not None else 'UTC'
        timezone = ZoneInfo(timezone_string)

        start_time = datetime.fromtimestamp(start_timestamp, timezone)
        next_time = bt.TIME_INTERVAL_FUNCTIONS[repeat_interval_index](start_time, repeat_interval_increment * new_repeat_interval_count)

        cursor.execute("""
            UPDATE reminders
            SET next_timestamp = ?, repeat_increment_count = ?
            WHERE name = ? AND channel_id = ?;
        """, (next_time.timestamp(), new_repeat_interval_count, name, channel_id))
        conn.commit()
    else: #reminder must not have repeat, so delete it
        cursor.execute("""
            DELETE FROM reminders WHERE name == ? AND channel_id == ? AND next_timestamp <= ? AND NOT has_repeat
        """, (name, channel_id, now_timestamp))
        conn.commit()
