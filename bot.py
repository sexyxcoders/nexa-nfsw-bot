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
# ENV CONFIG (SAFE)
# =====================================================
API_ID = int(os.getenv("API_ID", "22657083"))          # REQUIRED for Pyrogram
API_HASH = os.getenv("API_HASH", "d6186691704bd901bdab275ceaab88f3")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN missing")

PRIMARY_NSFW_API = "https://nexacoders-nexa-api.hf.space/scan"
FALLBACK_NSFW_API = os.getenv(
    "CF_NSFW_API",
    "https://nexacoders-nexa-api.hf.space/batch-scan"
)

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("NexaNSFW")

# =====================================================
# HTTP SESSION (REUSED)
# =====================================================
_http: aiohttp.ClientSession | None = None

async def get_http():
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=3)
        )
    return _http

# =====================================================
# FAST SAFE SKIP (HUGE SPEED BOOST)
# =====================================================
def fast_safe(msg: Message) -> bool:
    try:
        if msg.sticker and msg.sticker.file_size and msg.sticker.file_size < 30_000:
            return True
        if msg.photo and msg.photo.file_size and msg.photo.file_size < 40_000:
            return True
    except Exception:
        pass
    return False

# =====================================================
# IMAGE OPTIMIZATION (FASTER)
# =====================================================
def optimize_image(raw: bytes) -> bytes:
    if len(raw) < 50 * 1024:
        return raw
    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        img.thumbnail((160, 160))   # smaller = faster
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=75)
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
def strict_nsfw(scores: dict):
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
# NSFW API CALL (PRIMARY + FALLBACK)
# =====================================================
async def call_nsfw_api(image_bytes: bytes) -> dict | None:
    session = await get_http()

    async def _call(url):
        form = aiohttp.FormData()
        form.add_field("file", image_bytes, filename="scan.jpg", content_type="image/jpeg")
        async with session.post(url, data=form) as r:
            if r.status != 200:
                return None
            return await r.json()

    try:
        data = await _call(PRIMARY_NSFW_API)
        if data:
            return data
    except Exception:
        logger.warning("Primary NSFW API failed")

    try:
        data = await _call(FALLBACK_NSFW_API)
        if data:
            return data
    except Exception:
        logger.error("Fallback NSFW API failed")

    return None

# =====================================================
# CORE SCANNER
# =====================================================
async def scan_media(client: Client, msg: Message, manual=False):
    if not manual and fast_safe(msg):
        return False, None, "Fast-Safe"

    media, file_uid, use_thumb = None, None, False

    if msg.sticker:
        media = msg.sticker
        file_uid = media.file_unique_id
        if media.is_animated or media.is_video:
            use_thumb = True
            if not media.thumbs:
                return False, None, "No Thumbnail"

    elif msg.photo:
        media = msg.photo
        file_uid = media.file_unique_id

    elif msg.document and msg.document.mime_type and "image" in msg.document.mime_type:
        media = msg.document
        file_uid = media.file_unique_id

    else:
        return False, None, "Unsupported"

    if not manual:
        cached = await get_cached_scan(file_uid)
        if cached:
            verdict, reason = strict_nsfw(cached["data"]["scores"])
            return verdict, cached["data"], reason

    try:
        if use_thumb:
            mem = await client.download_media(media.thumbs[-1].file_id, in_memory=True)
        else:
            mem = await client.download_media(msg, in_memory=True)
        img = optimize_image(bytes(mem.getbuffer()))
    except Exception:
        return False, None, "Download Failed"

    data = await call_nsfw_api(img)
    if not data:
        return False, None, "API Unavailable"

    verdict, reason = strict_nsfw(data.get("scores", {}))
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
# START (PRIVATE)
# =====================================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(_, msg: Message):
    await msg.reply_text(
        "🤖 **Nexa NSFW Bot**\n\n"
        "🛡 AI-Powered Content Protection\n"
        "⚡ Fast | ☁️ Cloud-Backed | 🔥 Smart\n\n"
        "Commands:\n"
        "/scan (reply to media)\n"
        "/nsfw on | off (groups)"
    )

# =====================================================
# NSFW TOGGLE
# =====================================================
@app.on_message(filters.command("nsfw") & filters.group)
@AdminRights("can_delete_messages")
async def nsfw_toggle(_, msg: Message):
    if len(msg.command) < 2:
        state = await get_nsfw_status(msg.chat.id)
        await msg.reply_text(f"🛡 NSFW System: `{'Enabled' if state else 'Disabled'}`")
        return

    enable = msg.command[1].lower() in ("on", "enable")
    await set_nsfw_status(msg.chat.id, enable)
    await msg.reply_text("✅ NSFW Enabled" if enable else "❌ NSFW Disabled")

# =====================================================
# MANUAL SCAN
# =====================================================
@app.on_message(filters.command("scan") & filters.reply)
async def manual_scan(client: Client, msg: Message):
    status = await msg.reply_text("⚡ Scanning…")
    start = time.time()

    verdict, data, reason = await scan_media(client, msg.reply_to_message, manual=True)
    took = time.time() - start

    if not data:
        await status.edit("❌ Scan failed")
        return

    bar = "🟥" if verdict else "🟩"
    await status.edit(
        f"{'🚨 UNSAFE' if verdict else '✅ SAFE'}\n"
        f"⏱ `{took:.3f}s`\n"
        f"🔎 `{reason}`\n"
        f"{bar * 12}\n\n"
        f"{format_scores(data['scores'])}"
    )
    await asyncio.sleep(20)
    await status.delete()

# =====================================================
# AUTO WATCHER (NON-BLOCKING)
# =====================================================
@app.on_message(filters.group & (filters.photo | filters.sticker | filters.document))
async def auto_nsfw(client: Client, msg: Message):
    if not await get_nsfw_status(msg.chat.id):
        return

    async def worker():
        verdict, data, reason = await scan_media(client, msg)
        if not verdict or not data:
            return
        try:
            await msg.delete()
        except:
            return
        info = await client.send_message(
            msg.chat.id,
            f"🚨 NSFW Removed\n"
            f"👤 {msg.from_user.mention}\n"
            f"🔎 `{reason}`\n\n"
            f"{format_scores(data['scores'])}"
        )
        await asyncio.sleep(20)
        await info.delete()

    asyncio.create_task(worker())

# =====================================================
# STARTUP
# =====================================================
logger.info("🤖 Nexa NSFW Bot Loaded Successfully")
logger.info("🚀 Developed by Team Nexa")
logger.info("🛡 AI Protection Active")

app.run()