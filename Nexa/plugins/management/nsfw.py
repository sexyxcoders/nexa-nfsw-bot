import asyncio
import io
import aiohttp
from PIL import Image

from pyrogram import Client, filters
from pyrogram.types import Message

from config import NSFW_API_URL, NSFW_THRESHOLD, LOG_DELETE_TIME
from Nexa.database.client import (
    get_nsfw_status,
    set_nsfw_status,
    get_cached_scan,
    cache_scan_result
)
from Nexa.database.redis import redis_get, redis_set
from Nexa.utils.decorators import admin_only
from Nexa.core.session import get_session

# ───────────────── IMAGE OPTIMIZATION ─────────────────

def optimize_image(data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue()
    except Exception:
        return data


# ───────────────── UI ─────────────────

def score_ui(scores: dict) -> str:
    return (
        f"😐 Neutral    : {scores.get('neutral', 0.0)*100:05.2f}%\n"
        f"🔞 Porn       : {scores.get('porn', 0.0)*100:05.2f}%\n"
        f"💋 Sexy       : {scores.get('sexy', 0.0)*100:05.2f}%\n"
        f"🎨 Drawings   : {scores.get('drawings', 0.0)*100:05.2f}%\n"
        f"👾 Hentai     : {scores.get('hentai', 0.0)*100:05.2f}%"
    )


# ───────────────── DETECTION ─────────────────

def is_nsfw(scores: dict):
    for k in ("porn", "sexy", "hentai"):
        if scores.get(k, 0.0) >= NSFW_THRESHOLD:
            return True, f"{k.upper()} ({scores[k]*100:.2f}%)"
    return False, "SAFE"


# ───────────────── COMMANDS ─────────────────

@Client.on_message(filters.command("nsfw") & filters.group)
@admin_only
async def nsfw_toggle(_, m: Message):
    if len(m.command) < 2:
        state = await get_nsfw_status(m.chat.id)
        return await m.reply(
            f"🔞 **NSFW is {'ENABLED' if state else 'DISABLED'}**"
        )

    arg = m.command[1].lower()
    if arg in ("on", "enable"):
        await set_nsfw_status(m.chat.id, True)
        await m.reply("✅ **NSFW ENABLED**")
    elif arg in ("off", "disable"):
        await set_nsfw_status(m.chat.id, False)
        await m.reply("🛑 **NSFW DISABLED**")


@Client.on_message(filters.command("scan") & filters.group)
@admin_only
async def manual_scan(client: Client, m: Message):
    if not m.reply_to_message:
        return await m.reply("❌ Reply to an image or video")

    await scan_media(client, m.reply_to_message, force=True)


# ───────────────── WATCHER ─────────────────

@Client.on_message(
    filters.group & (filters.photo | filters.video | filters.document),
    group=5
)
async def nsfw_watcher(client: Client, m: Message):
    if not await get_nsfw_status(m.chat.id):
        return
    await scan_media(client, m)


# ───────────────── CORE SCAN LOGIC ─────────────────

async def scan_media(client: Client, m: Message, force: bool = False):
    media = m.photo or m.video or m.document
    if not media:
        return

    file_id = media.file_unique_id

    # ── Redis cache
    if not force:
        r = redis_get(file_id)
        if r:
            if r.get("bad"):
                await m.delete()
            return

    # ── Mongo cache
    if not force:
        mongo = await get_cached_scan(file_id)
        if mongo and mongo.get("safe"):
            redis_set(file_id, {"bad": False})
            return

    # ── Download
    try:
        buf = await client.download_media(m, in_memory=True)
        data = buf.getvalue()
    except Exception:
        return

    # ── Convert video → first frame not supported → skip heavy processing
    if m.video:
        return  # optional: add ffmpeg later

    img = optimize_image(data)

    # ── API Scan
    try:
        session = await get_session()
        form = aiohttp.FormData()
        form.add_field(
            "file",
            img,
            filename="scan.jpg",
            content_type="image/jpeg"
        )

        async with session.post(NSFW_API_URL, data=form, timeout=6) as r:
            if r.status != 200:
                return
            result = await r.json()
    except Exception:
        return

    scores = result.get("scores", {})
    bad, reason = is_nsfw(scores)

    redis_set(file_id, {"bad": bad})
    await cache_scan_result(file_id, not bad, result)

    if not bad:
        return

    # ── INSTANT DELETE (≥2%)
    await m.delete()

    user = m.from_user.mention if m.from_user else "Deleted Account"

    log = await client.send_message(
        m.chat.id,
        f"🚨 **NSFW REMOVED**\n"
        f"👤 User: {user}\n"
        f"⚠️ Reason: {reason}\n\n"
        f"{score_ui(scores)}\n\n"
        f"⚡ Powered by **NexaCoders**"
    )

    await asyncio.sleep(LOG_DELETE_TIME)
    await log.delete()