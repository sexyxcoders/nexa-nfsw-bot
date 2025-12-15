import aiohttp
import asyncio
import io
from PIL import Image

from pyrogram import Client, filters
from pyrogram.types import Message

from config import (
    NSFW_API_URL,
    NSFW_THRESHOLD,
    LOG_DELETE_TIME
)

from Nexa.database.client import (
    get_nsfw_status,
    set_nsfw_status,
    get_cached_scan,
    cache_scan_result
)

from Nexa.database.redis import redis_get, redis_set
from Nexa.utils.decorators import admin_only
from Nexa.core.session import get_session

# ───────── IMAGE OPTIMIZATION ─────────

def optimize_image(data: bytes) -> bytes:
    try:
        if len(data) < 40 * 1024:
            return data
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue()
    except:
        return data

# ───────── UI FORMAT ─────────

def score_ui(s: dict) -> str:
    return (
        f"😐 Neutral    : {s.get('neutral',0)*100:05.2f}%\n"
        f"🔞 Porn       : {s.get('porn',0)*100:05.2f}%\n"
        f"💋 Sexy       : {s.get('sexy',0)*100:05.2f}%\n"
        f"🎨 Drawings   : {s.get('drawings',0)*100:05.2f}%\n"
        f"👾 Hentai     : {s.get('hentai',0)*100:05.2f}%"
    )

# ───────── DETECTION LOGIC ─────────

def is_nsfw(scores: dict):
    if scores.get("porn", 0) >= NSFW_THRESHOLD:
        return True, f"Pornographic Content ({scores['porn']*100:.2f}%)"
    if scores.get("hentai", 0) >= NSFW_THRESHOLD:
        return True, f"Hentai Content ({scores['hentai']*100:.2f}%)"
    if scores.get("sexy", 0) >= NSFW_THRESHOLD:
        return True, f"Sexual Content ({scores['sexy']*100:.2f}%)"
    return False, "Safe"

# ───────── NSFW TOGGLE ─────────

@Client.on_message(filters.command("nsfw") & filters.group)
@admin_only
async def nsfw_toggle(_, m: Message):
    if len(m.command) == 1:
        state = await get_nsfw_status(m.chat.id)
        return await m.reply(f"🔞 NSFW is **{'ON' if state else 'OFF'}**")

    arg = m.command[1].lower()
    if arg in ("on", "enable"):
        await set_nsfw_status(m.chat.id, True)
        await m.reply("✅ NSFW **ENABLED**")
    elif arg in ("off", "disable"):
        await set_nsfw_status(m.chat.id, False)
        await m.reply("❌ NSFW **DISABLED**")

# ───────── WATCHER (FIXED FILTERS) ─────────

@Client.on_message(
    filters.group & (
        filters.photo |
        filters.sticker |
        (filters.document & filters.regex(r".*\.(jpg|jpeg|png|webp)$"))
    ),
    group=3
)
async def nsfw_watcher(client: Client, m: Message):

    if not await get_nsfw_status(m.chat.id):
        return

    media = m.photo or m.sticker or m.document
    file_id = media.file_unique_id

    # ⚡ Redis fast cache
    r = redis_get(file_id)
    if r:
        if r.get("bad"):
            await m.delete()
        return

    # 🧠 Mongo safe cache
    cached = await get_cached_scan(file_id)
    if cached and cached.get("safe") is True:
        redis_set(file_id, {"bad": False})
        return

    # 📥 Download
    try:
        f = await client.download_media(m, in_memory=True)
        img = optimize_image(f.getvalue())
    except:
        return

    # 🌐 API Scan
    try:
        session = await get_session()
        form = aiohttp.FormData()
        form.add_field("file", img, filename="scan.jpg", content_type="image/jpeg")

        async with session.post(NSFW_API_URL, data=form, timeout=5) as resp:
            if resp.status != 200:
                return
            result = await resp.json()
    except:
        return

    scores = result.get("scores", {})
    bad, reason = is_nsfw(scores)

    redis_set(file_id, {"bad": bad})
    await cache_scan_result(file_id, not bad, result)

    if not bad:
        return

    # 🚨 DELETE & LOG
    await m.delete()

    user = m.from_user.mention if m.from_user else "Deleted Account"

    log = await client.send_message(
        m.chat.id,
        f"🚨 **NSFW Removed**\n"
        f"👤 User: {user}\n"
        f"🔎 {reason}\n\n"
        f"{score_ui(scores)}\n\n"
        f"⚡ Powered by **Nexa**"
    )

    await asyncio.sleep(LOG_DELETE_TIME)
    await log.delete()