import os
import io
import time
import asyncio
import logging
import aiohttp
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
# ENV CONFIG
# =====================================================
API_ID = int(os.getenv("API_ID", "22657083"))
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
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("NexaNSFW")

# =====================================================
# HTTP SESSION (FAST + SAFE)
# =====================================================
_http: aiohttp.ClientSession | None = None

async def get_http():
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=2,
                connect=1,
                sock_read=1
            )
        )
    return _http

# =====================================================
# FAST SAFE SKIP (MAJOR SPEED BOOST)
# =====================================================
def fast_safe(msg: Message) -> bool:
    try:
        if msg.photo and msg.photo.file_size < 60_000:
            return True

        if msg.sticker:
            if msg.sticker.is_animated or msg.sticker.is_video:
                return True
            if msg.sticker.file_size < 50_000:
                return True

        if msg.photo and msg.photo.width <= 320:
            return True
    except Exception:
        pass

    return False

# =====================================================
# EXTREME IMAGE OPTIMIZATION
# =====================================================
def optimize_image(raw: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((96, 96))  # 🔥 ULTRA FAST
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=60, optimize=True)
        return buf.getvalue()
    except Exception:
        return raw[:30_000]

# =====================================================
# STRICT NSFW DECISION (2%)
# =====================================================
def strict_nsfw(scores: dict):
    porn = scores.get("porn", 0)
    hentai = scores.get("hentai", 0)

    if porn >= 0.02:
        return True, "Porn Content ≥2%"

    if hentai >= 0.02:
        return True, "Hentai Content ≥2%"

    return False, "Safe"

# =====================================================
# NSFW API CALL
# =====================================================
async def call_nsfw_api(image: bytes) -> dict | None:
    session = await get_http()

    async def _call(url):
        form = aiohttp.FormData()
        form.add_field("file", image, filename="scan.jpg", content_type="image/jpeg")
        async with session.post(url, data=form) as r:
            if r.status != 200:
                return None
            return await r.json()

    try:
        data = await _call(PRIMARY_NSFW_API)
        if data:
            return data
    except Exception:
        pass

    try:
        data = await _call(FALLBACK_NSFW_API)
        if data:
            return data
    except Exception:
        pass

    return None

# =====================================================
# CORE SCAN FUNCTION
# =====================================================
async def scan_media(client: Client, msg: Message, manual=False):
    if not manual and fast_safe(msg):
        return False, None, "Fast-Safe"

    media = None
    file_uid = None
    use_thumb = False

    if msg.photo:
        media = msg.photo
        file_uid = media.file_unique_id

    elif msg.sticker:
        media = msg.sticker
        file_uid = media.file_unique_id
        if media.is_video or media.is_animated:
            use_thumb = True
            if not media.thumbs:
                return False, None, "No Thumb"

    elif msg.document and msg.document.mime_type and "image" in msg.document.mime_type:
        media = msg.document
        file_uid = media.file_unique_id

    else:
        return False, None, "Unsupported"

    if not manual:
        cached = await get_cached_scan(file_uid)
        if cached:
            verdict, reason = strict_nsfw(cached["data"]["scores"])
            return verdict, cached["data"], "Cached"

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
        return False, None, "API Error"

    verdict, reason = strict_nsfw(data.get("scores", {}))
    await cache_scan_result(file_uid, not verdict, data)

    return verdict, data, reason

# =====================================================
# BOT CLIENT
# =====================================================
app = Client(
    "nexa_nsfw_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# =====================================================
# START
# =====================================================
@app.on_message(filters.command("start") & filters.private)
async def start(_, msg: Message):
    await msg.reply_text(
        "🤖 **Nexa NSFW Bot**\n\n"
        "⚡ Ultra Fast Mode Enabled\n"
        "🔞 Porn & Hentai ≥2% Auto Delete\n\n"
        "Commands:\n"
        "/scan (reply to image)\n"
        "/nsfw on | off"
    )

# =====================================================
# NSFW TOGGLE
# =====================================================
@app.on_message(filters.command("nsfw") & filters.group)
@AdminRights("can_delete_messages")
async def nsfw_toggle(_, msg: Message):
    if len(msg.command) < 2:
        state = await get_nsfw_status(msg.chat.id)
        await msg.reply_text(f"🛡 NSFW: `{'ON' if state else 'OFF'}`")
        return

    enable = msg.command[1].lower() in ("on", "enable")
    await set_nsfw_status(msg.chat.id, enable)
    await msg.reply_text("✅ NSFW Enabled" if enable else "❌ NSFW Disabled")

# =====================================================
# MANUAL SCAN
# =====================================================
@app.on_message(filters.command("scan") & filters.reply)
async def manual_scan(client: Client, msg: Message):
    status = await msg.reply_text("⚡ Scanning...")
    start = time.time()

    verdict, data, reason = await scan_media(client, msg.reply_to_message, manual=True)

    if not data:
        await status.edit("❌ Scan Failed")
        return

    took = time.time() - start
    await status.edit(
        f"{'🚨 NSFW' if verdict else '✅ SAFE'}\n"
        f"⏱ `{took:.3f}s`\n"
        f"🔎 `{reason}`"
    )

    await asyncio.sleep(15)
    await status.delete()

# =====================================================
# AUTO GROUP WATCHER (NON BLOCKING)
# =====================================================
@app.on_message(filters.group & (filters.photo | filters.sticker | filters.document))
async def auto_nsfw(client: Client, msg: Message):
    if not await get_nsfw_status(msg.chat.id):
        return

    async def worker():
        verdict, data, reason = await scan_media(client, msg)
        if not verdict:
            return

        try:
            await msg.delete()
        except Exception:
            return

        asyncio.create_task(
            client.send_message(
                msg.chat.id,
                f"🚨 NSFW Removed\n"
                f"👤 {msg.from_user.mention}\n"
                f"🔎 `{reason}`"
            )
        )

    asyncio.create_task(worker())

# =====================================================
# STARTUP
# =====================================================
log.info("🚀 Nexa NSFW Bot Started (ULTRA FAST MODE)")
app.run()