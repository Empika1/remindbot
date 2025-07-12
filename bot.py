import asyncio

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

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    await message.channel.send("waiting for embeds to potentially be removed")

    await asyncio.sleep(5)

    # print(len(message.embeds))
    # message = await message.channel.fetch_message(message.id)
    # print(len(message.embeds))

    message_files = [await attachment.to_file() for attachment in message.attachments]

    await message.channel.send(content=message.content, tts=message.tts, 
                               embed=message.embeds[0] if len(message.embeds) == 1 else None, embeds=message.embeds if len(message.embeds) > 1 else None,
                               file=message_files[0] if len(message_files) == 1 else None, files=message_files if len(message_files) > 1 else None, 
                               stickers=message.stickers, reference=message.reference, 
                               suppress_embeds = len(message.embeds) == 0,
                               poll=message.poll)

# @client.event
# async def on_message_edit(before, after):
#     print(len(before.embeds), len(after.embeds))

client.run(token)
