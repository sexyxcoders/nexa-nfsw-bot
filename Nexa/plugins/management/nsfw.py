import aiohttp, asyncio, io
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message

from Nexa.database.client import (
    set_nsfw_status,
    get_nsfw_status,
    get_cached_scan,
    cache_scan_result
)
from Nexa.database.redis import redis_get, redis_set
from Nexa.utils.decorators import admin_only
from Nexa.core.session import get_session

NSFW_API = "https://nexacoders-nexa-api.hf.space/scan"

# ---------- IMAGE OPT ----------

def optimize_image(data: bytes) -> bytes:
    if len(data) < 40 * 1024:
        return data
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=80)
        return out.getvalue()
    except:
        return data

# ---------- UI ----------

def score_ui(s: dict) -> str:
    return (
        f"😐 Neutral    : {s.get('neutral',0)*100:05.2f}%\n"
        f"🔞 Porn       : {s.get('porn',0)*100:05.2f}%\n"
        f"💋 Sexy       : {s.get('sexy',0)*100:05.2f}%\n"
        f"🎨 Drawings   : {s.get('drawings',0)*100:05.2f}%\n"
        f"👾 Hentai     : {s.get('hentai',0)*100:05.2f}%"
    )

# ---------- DETECT ----------

def detect(scores: dict):
    if scores.get("porn",0) >= 0.02:
        return True, f"Pornographic Content ({scores['porn']*100:.2f}%)"
    if scores.get("hentai",0) >= 0.02:
        return True, f"Hentai Content ({scores['hentai']*100:.2f}%)"
    if scores.get("sexy",0) >= 0.02:
        return True, f"Sexual Content ({scores['sexy']*100:.2f}%)"
    return False, "Safe"

# ---------- COMMAND ----------

@Client.on_message(filters.command("nsfw") & filters.group)
@admin_only
async def nsfw_toggle(_, m: Message):
    if len(m.command) < 2:
        state = await get_nsfw_status(m.chat.id)
        return await m.reply(f"🔞 NSFW is **{'ON' if state else 'OFF'}**")

    if m.command[1].lower() in ("on", "enable"):
        await set_nsfw_status(m.chat.id, True)
        await m.reply("🚀 NSFW ENABLED")
    elif m.command[1].lower() in ("off", "disable"):
        await set_nsfw_status(m.chat.id, False)
        await m.reply("🛑 NSFW DISABLED")

# ---------- WATCHER ----------

@Client.on_message(
    filters.group & (filters.photo | filters.sticker | filters.document & filters.mime_type("image/")),
    group=3
)
async def nsfw_watch(client: Client, m: Message):
    if not await get_nsfw_status(m.chat.id):
        return

    media = m.photo or m.sticker or m.document
    fid = media.file_unique_id

    # Redis fast path
    r = redis_get(fid)
    if r:
        if r["bad"]:
            await m.delete()
        return

    # Mongo safe
    cached = await get_cached_scan(fid)
    if cached and cached.get("safe") is True:
        redis_set(fid, {"bad": False})
        return

    try:
        f = await client.download_media(m, in_memory=True)
        img = optimize_image(f.getvalue())
    except:
        return

    try:
        s = await get_session()
        form = aiohttp.FormData()
        form.add_field("file", img, filename="scan.jpg", content_type="image/jpeg")
        async with s.post(NSFW_API, data=form, timeout=5) as r:
            if r.status != 200:
                return
            data = await r.json()
    except:
        return

    scores = data.get("scores", {})
    bad, reason = detect(scores)

    redis_set(fid, {"bad": bad})
    await cache_scan_result(fid, not bad, data)

    if not bad:
        return

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

    await asyncio.sleep(15)
    await log.delete()