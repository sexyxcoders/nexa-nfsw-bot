import os
import logging
import asyncio
import aiohttp
import io
import time
from PIL import Image

from pyrogram import Client, filters
from pyrogram.types import Message

from Nexa.utils.decorators import AdminRights
from Nexa.database.client import (
    set_nsfw_status,
    get_nsfw_status,
    get_cached_scan,
    cache_scan_result
)

# =====================================================
# CONFIG
# =====================================================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

NSFW_API_URL = "https://nexacoders-nexa-api.hf.space/scan"

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("NexaNSFW")

# =====================================================
# GLOBAL HTTP SESSION
# =====================================================
_http: aiohttp.ClientSession | None = None


async def get_http():
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession()
    return _http


# =====================================================
# IMAGE OPTIMIZATION
# =====================================================
def optimize_image(raw: bytes) -> bytes:
    if len(raw) < 50 * 1024:
        return raw

    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        img.thumbnail((256, 256))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return buf.getvalue()
    except Exception:
        return raw


# =====================================================
# SCORE FORMATTER
# =====================================================
def format_scores(scores: dict) -> str:
    icons = {
        "neutral": "😐",
        "drawings": "🎨",
        "sexy": "💋",
        "porn": "🔞",
        "hentai": "👾",
    }

    return "\n".join(
        f"{icons.get(k,'🔹')} `{k.title():10} : {v*100:05.2f}%`"
        for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    )


# =====================================================
# NSFW DECISION ENGINE
# =====================================================
def strict_nsfw_check(scores: dict):
    porn = scores.get("porn", 0)
    hentai = scores.get("hentai", 0)
    sexy = scores.get("sexy", 0)

    if porn > 0.08:
        return True, "Pornographic Content"
    if hentai > 0.15:
        return True, "Hentai Content"
    if sexy > 0.45:
        return True, "Explicit Content"
    if porn + hentai + sexy > 0.40:
        return True, "High Risk NSFW"

    return False, "Safe"


# =====================================================
# CORE SCANNER
# =====================================================
async def scan_media(client: Client, message: Message, manual=False):
    media = None
    file_uid = None
    use_thumb = False

    if message.sticker:
        media = message.sticker
        file_uid = media.file_unique_id
        if media.is_animated or media.is_video:
            use_thumb = True
            if not media.thumbs:
                return False, None, "No Thumbnail"

    elif message.photo:
        media = message.photo
        file_uid = media.file_unique_id

    elif message.document and message.document.mime_type:
        if "image" in message.document.mime_type:
            media = message.document
            file_uid = media.file_unique_id
        else:
            return False, None, "Unsupported File"

    else:
        return False, None, "Unsupported Media"

    # ---------- CACHE ----------
    if not manual:
        cached = await get_cached_scan(file_uid)
        if cached:
            verdict, reason = strict_nsfw_check(cached["data"]["scores"])
            return verdict, cached["data"], reason

    # ---------- DOWNLOAD ----------
    try:
        if use_thumb:
            thumb = media.thumbs[-1]
            mem = await client.download_media(thumb.file_id, in_memory=True)
        else:
            mem = await client.download_media(message, in_memory=True)

        raw = bytes(mem.getbuffer())
        img = optimize_image(raw)

    except Exception:
        return False, None, "Download Failed"

    # ---------- API ----------
    try:
        session = await get_http()
        form = aiohttp.FormData()
        form.add_field("file", img, filename="scan.jpg", content_type="image/jpeg")

        async with session.post(NSFW_API_URL, data=form, timeout=6) as r:
            if r.status != 200:
                return False, None, "API Error"
            data = await r.json()

    except Exception:
        return False, None, "Connection Error"

    verdict, reason = strict_nsfw_check(data.get("scores", {}))
    await cache_scan_result(file_uid, not verdict, data)
    return verdict, data, reason


# =====================================================
# PYROGRAM CLIENT
# =====================================================
app = Client(
    "nexa_nsfw_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# =====================================================
# COMMANDS
# =====================================================
@app.on_message(filters.command("nsfw") & filters.group)
@AdminRights("can_delete_messages")
async def nsfw_toggle(_, msg: Message):
    if len(msg.command) < 2:
        state = await get_nsfw_status(msg.chat.id)
        await msg.reply_text(
            f"🛡 **NSFW System:** `{'Enabled' if state else 'Disabled'}`\n"
            "Usage: `/nsfw on` or `/nsfw off`"
        )
        return

    arg = msg.command[1].lower()
    await set_nsfw_status(msg.chat.id, arg in ("on", "enable"))
    await msg.reply_text("✅ NSFW Enabled" if arg in ("on", "enable") else "❌ NSFW Disabled")


# =====================================================
# MANUAL SCAN
# =====================================================
@app.on_message(filters.command("scan") & filters.reply)
async def manual_scan(client: Client, msg: Message):
    status = await msg.reply_text("⚡ **Scanning…**")
    start = time.time()

    verdict, data, reason = await scan_media(client, msg.reply_to_message, manual=True)
    took = time.time() - start

    if not data:
        await status.edit("❌ Scan failed")
        return

    bar = "🟥" if verdict else "🟩"
    text = (
        f"{'🚨 **UNSAFE**' if verdict else '✅ **SAFE**'}\n"
        f"⏱️ Time: `{took:.3f}s`\n"
        f"🔎 Verdict: `{reason}`\n"
        f"{bar * 12}\n\n"
        f"📊 **Confidence Scores:**\n{format_scores(data['scores'])}"
    )

    await status.edit(text)
    await asyncio.sleep(20)
    await status.delete()


# =====================================================
# AUTO WATCHER
# =====================================================
@app.on_message(filters.group & (filters.photo | filters.sticker | filters.document))
async def auto_nsfw(client: Client, msg: Message):
    if not await get_nsfw_status(msg.chat.id):
        return

    verdict, data, reason = await scan_media(client, msg)
    if not verdict or not data:
        return

    try:
        await msg.delete()
    except Exception:
        return

    info = await client.send_message(
        msg.chat.id,
        f"🚨 **NSFW Content Removed**\n"
        f"👤 User: {msg.from_user.mention}\n"
        f"🔎 Reason: `{reason}`\n\n"
        f"📊 **AI Analysis:**\n{format_scores(data['scores'])}"
    )

    await asyncio.sleep(20)
    await info.delete()


# =====================================================
# STARTUP
# =====================================================
logger.info("=" * 50)
logger.info("🤖 Nexa NSFW Bot Loaded Successfully")
logger.info("🚀 Developed by Team Nexa")
logger.info("🛡️ AI-Powered Content Protection Active")
logger.info("=" * 50)

print("==============================================")
print("🤖 Nexa NSFW Bot Loaded Successfully")
print("🚀 Developed by Team Nexa")
print("🛡️ AI-Powered Content Protection Active")
print("==============================================")

app.run()