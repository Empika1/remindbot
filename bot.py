from datetime import datetime
from typing import cast
import discord
from discord.ext import tasks
import bot_io as bi
import bot_db as bd
import bot_response as br
import bot_permissions as bp
import bot_log as bl

token = ''
try:
    with open('token.txt', 'r') as f:
        token = f.read()
except OSError:
    print("token.txt failed to be opened")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

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
async def on_message(message: discord.message.Message):
    try:
        if message.author == client.user:
            return

        response = None
        try:
            perms = bp.ADMIN
            #permissions don't matter in a dm channel
            if not isinstance(message.channel, discord.DMChannel):
                perms = message.channel.permissions_for(cast(discord.Member, message.author)) #will always be a member if not in a dm channel

            response = bi.parse_command(message.content, 
                                        message.channel.id, 
                                        message.author.id, 
                                        message.author.name,
                                        perms,
                                        message.reference.message_id if message.reference is not None else None)
            if response is None:
                return
        except Exception as e:
            response = br.Response(
                is_error=True,
                title="An unexpected error occured..",
                txt=str(e)
            )

        await message.channel.send(embed=response.make_embed())
    except Exception as e:
        bl.log_err(e) 

@tasks.loop(seconds=5)
async def event_loop():
    now = datetime.now()
    while True: #so the bot can send multiple repeats of a reminder in one event loop
        try:
            due_reminders = bd.get_due_reminders(now)
            if len(due_reminders) == 0:
                break

            for (name, channel_id, reply_message_id, setter_user_id, start_timestamp, next_timestamp, 
            has_repeat, repeat_interval_index, repeat_interval_increment, repeat_increment_count) in due_reminders:
                # type ignores are because any channel in the database must be messageable already, so the type checking is busted
                channel = None
                try:
                    channel = await client.fetch_channel(channel_id)
                except discord.NotFound as e: #The channel was deleted #TODO: figure out if there is any other way for this exception to be raised
                    bd.remove_reminder(name, channel_id) #reminder no longer applicable

                reminder_response = br.Response(
                    title=f"Reminder: {name}"
                )

                reply_message = None
                if reply_message_id is not None:
                    try:
                        reply_message = await channel.fetch_message(reply_message_id) # type: ignore
                    except discord.NotFound as e: #The reply was deleted #TODO: figure out if there is any other way for this exception to be raised
                        reminder_response.warnings.append("The custom message for this reminder was deleted.")

                await channel.send(embed=reminder_response.make_embed()) # type: ignore

                if reply_message is not None:
                    await channel.send(**await copy_message(reply_message)) # type: ignore
            
                bd.update_reminder(name, channel_id, now)
        except Exception as e:
            bl.log_err(e) #for truly odd errors

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    event_loop.start()

client.run(token)
