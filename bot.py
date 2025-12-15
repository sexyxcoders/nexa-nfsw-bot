from pyrogram import Client
from Nexa.database.client import init_db
import os

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not API_ID:
    raise RuntimeError("API_ID missing")

app = Client(
    "nexa-nsfw-bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="Nexa.plugins")
)

init_db()
print("✅ Nexa NSFW Bot started")
app.run()