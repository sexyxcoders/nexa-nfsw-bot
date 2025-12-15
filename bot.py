import os
import asyncio
from pyrogram import Client
from Nexa.database.client import init_db

# ───── LOAD ENV SAFELY ─────
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ───── HARD FAIL IF MISSING (IMPORTANT) ─────
if not API_ID:
    raise RuntimeError("❌ API_ID is missing in environment variables")

if not API_HASH:
    raise RuntimeError("❌ API_HASH is missing in environment variables")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is missing in environment variables")

# ───── PYROGRAM CLIENT ─────
app = Client(
    name="nexa-nsfw-bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="Nexa.plugins")
)

# ───── INIT DATABASE ─────
asyncio.get_event_loop().run_until_complete(init_db())

# ───── START BOT ─────
print("✅ Nexa NSFW Bot started successfully")
app.run()