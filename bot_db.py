from datetime import datetime
import sqlite3
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
    has_repeat BOOLEAN NOT NULL,
    repeat_interval_index INTEGER,
    repeat_interval_increment INTEGER,
    repeat_increment_count INTEGER,
    next_timestamp INTEGER,
    PRIMARY KEY (name, channel_id),
    CHECK (NOT has_repeat OR repeat_interval_index IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_interval_increment IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_interval_increment > 0),
    CHECK (NOT has_repeat OR repeat_increment_count IS NOT NULL),
    CHECK (NOT has_repeat OR repeat_increment_count >= 0),
    CHECK (NOT has_repeat OR next_timestamp IS NOT NULL)
);
               
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL
);
""")

class ReminderAlreadyExistsError(Exception):
    pass

def add_reminder(name: str, channel_id: int, reply_message_id: int|None, user_id: int,
                 start_time: datetime, repeat_interval_index: int|None, repeat_interval_increment: int|None):
    cursor.execute("""
        SELECT 1 FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    
    if cursor.fetchone():
        raise ReminderAlreadyExistsError(f"Reminder with name '{name}' already exists in channel {channel_id}")

    cursor.execute("""
    INSERT INTO reminders (name, channel_id, reply_message_id, setter_user_id, start_timestamp, has_repeat,
                           repeat_interval_index, repeat_interval_increment, repeat_increment_count, next_timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (name, 
      channel_id,
      reply_message_id,
      user_id,
      start_time.timestamp(),
      repeat_interval_index != None,
      repeat_interval_index,
      repeat_interval_increment,
      0,
      bt.TIME_INTERVAL_FUNCTIONS[repeat_interval_index](start_time, 1) if repeat_interval_index != None else None))
    conn.commit()

class ReminderDoesntExistError(Exception):
    pass

def remove_reminder(name: str, channel_id: int):
    # Check if the reminder exists and get the setter's user ID
    cursor.execute("""
        SELECT setter_user_id FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    
    row = cursor.fetchone()
    if not row:
        raise ReminderDoesntExistError(f"Reminder with name '{name}' doesn't exist in channel {channel_id}")

    # Perform the deletion
    cursor.execute("""
        DELETE FROM reminders WHERE name = ? AND channel_id = ?
    """, (name, channel_id))
    conn.commit()

def get_all_reminders(channel_id: int) -> list:
    cursor.execute("""
        SELECT name FROM reminders WHERE channel_id = ?
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
    if row:
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
    if not row:
        raise UserNotInDatabaseError("User doesn't have a set timezone")

    # Perform the deletion
    cursor.execute("""
        DELETE FROM users WHERE id = ?
    """, (user_id,))
    conn.commit()