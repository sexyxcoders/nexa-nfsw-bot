import aiohttp, asyncio, io, json
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
    for k in ("porn", "hentai", "sexy"):
        if scores.get(k, 0) >= NSFW_THRESHOLD:
            return True, f"{k.title()} Content ({scores[k]*100:.2f}%)"
    return False, "Safe"


# ---------- COMMAND ----------

@Client.on_message(filters.command("nsfw") & filters.group)
@admin_only
async def nsfw_toggle(_, m: Message):
    if len(m.command) < 2:
        state = get_nsfw_status(m.chat.id)
        return await m.reply(f"🔞 NSFW is **{'ON' if state else 'OFF'}**")

    if m.command[1].lower() in ("on", "enable"):
        set_nsfw_status(m.chat.id, True)
        await m.reply("🚀 NSFW ENABLED")
    elif m.command[1].lower() in ("off", "disable"):
        set_nsfw_status(m.chat.id, False)
        await m.reply("🛑 NSFW DISABLED")


# ---------- WATCHER ----------

@Client.on_message(
    filters.group & (filters.photo | filters.sticker | (filters.document & filters.image)),
    group=3
)
async def nsfw_watch(client: Client, m: Message):
    if not get_nsfw_status(m.chat.id):
        return

    media = m.photo or m.sticker or m.document
    fid = media.file_unique_id

    # ---------- Redis FAST PATH ----------
    cached_redis = redis_get(fid)
    if cached_redis:
        data = json.loads(cached_redis)
        if data["bad"]:
            await m.delete()
        return

    # ---------- Mongo SAFE ----------
    cached_mongo = get_cached_scan(fid)
    if cached_mongo and cached_mongo.get("safe") is True:
        redis_set(fid, json.dumps({"bad": False}))
        return

    # ---------- DOWNLOAD ----------
    try:
        f = await client.download_media(media, in_memory=True)
        img = optimize_image(f.getvalue())
    except:
        return

    # ---------- API ----------
    try:
        session = await get_session()
        form = aiohttp.FormData()
        form.add_field("file", img, filename="scan.jpg", content_type="image/jpeg")

        async with session.post(NSFW_API_URL, data=form, timeout=5) as r:
            if r.status != 200:
                return
            data = await r.json()
    except:
        return

    scores = data.get("scores", {})
    bad, reason = detect(scores)

    redis_set(fid, json.dumps({"bad": bad}))
    cache_scan_result(fid, not bad, data)

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

    await asyncio.sleep(LOG_DELETE_TIME)
    await log.delete()