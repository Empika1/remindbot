from datetime import datetime
import discord
from discord.ext import tasks
import bot_io as bi
import bot_db as bd
import bot_response as br
import bot_permissions as bp

# application_id = 1393603955392647299
# public_key = '6da30fd7129bb4b05100ebf9aa8bfa1454c3d941d08281fc9e2043cc892dd2fa'
token = ''
try:
    with open('token.txt', 'r') as f:
        token = f.read()
except OSError:
    print("token.txt failed to be opened")
    exit(1)
# client_id = 1393603955392647299
# client_secret = ''
# try:
#     with open('client_secret.txt', 'r') as f:
#         client_secret = f.read()
# except OSError:
#     print("client_secret.txt failed to be opened")

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
    if message.author == client.user:
        return

    response = None
    try:
        perms = bp.ADMIN
        #permissions don't matter in a dm channel
        if not isinstance(message.channel, discord.DMChannel):
            perms = message.channel.permissions_for(message.author) # type: ignore

        response = bi.parse_command(message.content, 
                                    message.channel.id, 
                                    message.author.id, 
                                    message.author.name,
                                    perms,
                                    message.reference.message_id if message.reference is not None else None)
        if response is None:
            return
    except:
        response = br.Response(
            is_error=True,
            title="An unexpected error occured.."
        )

    await message.channel.send(embed=response.make_embed())

async def get_channel_or_dm(channel_id: int, user_id: int):
    channel = await client.fetch_channel(channel_id)
    if channel is None:
        user = await client.fetch_user(user_id)
        if user is None:
            return None
        channel = user.dm_channel
    return channel

@tasks.loop(seconds=5)
async def event_loop():
    now = datetime.now()
    while True:
        due_reminders = bd.get_due_reminders(now)
        if len(due_reminders) == 0:
            break

        for (name, channel_id, reply_message_id, setter_user_id, start_timestamp, next_timestamp, 
        has_repeat, repeat_interval_index, repeat_interval_increment, repeat_increment_count) in due_reminders:
            # type ignores are because any channel in the database must be messageable already, so the type checking is overkill
            channel = await get_channel_or_dm(channel_id, setter_user_id)

            reminder_response = br.Response(
                title=f"Reminder: {name}"
            )
            await channel.send(embed=reminder_response.make_embed()) # type: ignore

            if reply_message_id is not None:
                reply_message = await channel.fetch_message(reply_message_id) # type: ignore
                await channel.send(**await copy_message(reply_message)) # type: ignore
        
        bd.update_reminders(now)
    

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    event_loop.start()

client.run(token)
