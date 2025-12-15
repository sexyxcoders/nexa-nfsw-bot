import os
import asyncio
from pyrogram import Client
from Nexa.database.client import init_db

app = Client(
    "nexa-nsfw-bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN"),
    plugins=dict(root="Nexa.plugins")
)

asyncio.get_event_loop().run_until_complete(init_db())
app.run()