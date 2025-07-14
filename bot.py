import asyncio
import sqlite3

conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        message_id INTEGER PRIMARY KEY,
        channel_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        
    )
""")

import discord

application_id = 1393603955392647299
public_key = '6da30fd7129bb4b05100ebf9aa8bfa1454c3d941d08281fc9e2043cc892dd2fa'
token = ''
try:
    with open('token.txt', 'r') as f:
        token = f.read()
except OSError:
    print("token.txt failed to be opened")
client_id = 1393603955392647299
client_secret = ''
try:
    with open('client_secret.txt', 'r') as f:
        client_secret = f.read()
except OSError:
    print("client_secret.txt failed to be opened")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

async def copy_message(message):
    message_files = [await attachment.to_file() for attachment in message.attachments]

    return {
        'content' : message.content,
        'tts' : message.tts,
        'embed' : message.embeds[0] if len(message.embeds) == 1 else None,
        'embeds' : message.embeds if len(message.embeds) > 1 else None,
        'file' : message_files[0] if len(message_files) == 1 else None,
        'files' : message_files if len(message_files) > 1 else None,
        'stickers' : message.stickers,
        'reference' : message.reference,
        'suppress_embeds' : len(message.embeds) == 0,
        'poll' : message.poll
    }

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    try:
        await message.channel.send("waiting for embeds to potentially be removed")
    except:
        print("sending wait message failed")
        return

    await asyncio.sleep(5)

    cursor.execute("""
    INSERT INTO reminders (message_id, channel_id)
    VALUES (?, ?)
""", (message.id, message.channel.id))
    conn.commit()

    cursor.execute("SELECT message_id, channel_id FROM reminders")
    rows = cursor.fetchall()
    for row in rows:
        print(f"message_id={row[0]}, channel_id={row[1]}")

    copied_message = {}
    try:
        copied_message = await copy_message(message)
    except:
        print("copying message failed")
        return

    try:
        await message.channel.send(**copied_message)
    except:
        print("sending copycat message failed")
        return

client.run(token)
