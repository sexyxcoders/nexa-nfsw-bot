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

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID", "22657083"))
API_HASH = os.getenv("API_HASH", "d6186691704bd901bdab275ceaab88f3")
BOT_TOKEN = os.getenv("BOT_TOKEN")

NSFW_API_URL = "https://nexacoders-nexa-api.hf.space/scan"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NexaNSFW")

# ================= GLOBAL SESSION =================
aiohttp_session: aiohttp.ClientSession | None = None


async def get_session():
    global aiohttp_session
    if aiohttp_session is None or aiohttp_session.closed:
        aiohttp_session = aiohttp.ClientSession()
    return aiohttp_session


# ================= IMAGE OPTIMIZATION =================
def optimize_image(image_bytes: bytes) -> bytes:
    """
    Fast optimization:
    - Skip if already small
    - Resize to 256px JPEG (ViT friendly)
    """
    if len(image_bytes) < 50 * 1024:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=80)
        return out.getvalue()
    except Exception:
        return image_bytes


# ================= FORMATTER =================
def format_scores(scores: dict) -> str:
    icons = {
        "neutral": "😐",
        "drawings": "🎨",
        "sexy": "💋",
        "porn": "🔞",
        "hentai": "👾",
    }

    lines = []
    for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        icon = icons.get(k, "🔹")
        lines.append(f"{icon} `{k.title():10} : {v*100:05.2f}%`")

    return "\n".join(lines)


# ================= NSFW LOGIC =================
def strict_check(scores: dict):
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


# ================= CORE SCANNER =================
async def scan_media(client: Client, message: Message, manual=False):
    media = None
    file_id = None
    use_thumb = False

    if message.sticker:
        media = message.sticker
        file_id = media.file_unique_id
        if media.is_animated or media.is_video:
            use_thumb = True
            if not media.thumbs:
                return False, None, "No Thumbnail"

    elif message.photo:
        media = message.photo
        file_id = media.file_unique_id

    elif message.document and message.document.mime_type:
        if "image" in message.document.mime_type:
            media = message.document
            file_id = media.file_unique_id
        else:
            return False, None, "Not Image"

    else:
        return False, None, "Unsupported"

    # ---------- CACHE ----------
    if not manual:
        cached = await get_cached_scan(file_id)
        if cached:
            is_nsfw, reason = strict_check(cached["data"]["scores"])
            return is_nsfw, cached["data"], reason

    # ---------- DOWNLOAD ----------
    try:
        if use_thumb:
            thumb = media.thumbs[-1]
            mem = await client.download_media(thumb.file_id, in_memory=True)
        else:
            mem = await client.download_media(message, in_memory=True)

        raw = bytes(mem.getbuffer())
        image_bytes = optimize_image(raw)

    except Exception:
        return False, None, "Download Failed"

    # ---------- API ----------
    try:
        session = await get_session()
        form = aiohttp.FormData()
        form.add_field(
            "file",
            image_bytes,
            filename="scan.jpg",
            content_type="image/jpeg",
        )

        async with session.post(NSFW_API_URL, data=form, timeout=6) as r:
            if r.status != 200:
                return False, None, "API Error"
            data = await r.json()

    except Exception:
        return False, None, "Connection Error"

    scores = data.get("scores", {})
    is_nsfw, reason = strict_check(scores)

    await cache_scan_result(file_id, not is_nsfw, data)
    return is_nsfw, data, reason


# ================= PYROGRAM APP =================
app = Client(
    "nexa_nsfw_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ================= COMMANDS =================
@app.on_message(filters.command("nsfw") & filters.group)
@AdminRights("can_delete_messages")
async def nsfw_toggle(_, msg: Message):
    if len(msg.command) < 2:
        status = await get_nsfw_status(msg.chat.id)
        await msg.reply_text(
            f"🛡 **NSFW System:** `{'Enabled' if status else 'Disabled'}`\n"
            "Usage: `/nsfw on` or `/nsfw off`"
        )
        return

    arg = msg.command[1].lower()
    if arg in ("on", "enable"):
        await set_nsfw_status(msg.chat.id, True)
        await msg.reply_text("✅ NSFW protection enabled")
    elif arg in ("off", "disable"):
        await set_nsfw_status(msg.chat.id, False)
        await msg.reply_text("❌ NSFW protection disabled")


# ================= MANUAL SCAN =================
@app.on_message(filters.command("scan") & filters.reply)
async def manual_scan(client: Client, msg: Message):
    status = await msg.reply_text("⚡ **Scanning…**")
    start = time.time()

    is_nsfw, data, reason = await scan_media(client, msg.reply_to_message, manual=True)
    took = time.time() - start

    if not data:
        await status.edit("❌ Scan failed")
        return

    verdict = "🚨 **UNSAFE**" if is_nsfw else "✅ **SAFE**"
    bar = "🟥" if is_nsfw else "🟩"

    text = (
        f"{verdict}\n"
        f"⏱️ Time: `{took:.3f}s`\n"
        f"🔎 Verdict: `{reason}`\n"
        f"{bar * 12}\n\n"
        f"📊 **Confidence Scores:**\n"
        f"{format_scores(data.get('scores', {}))}"
    )

    await status.edit(text)
    await asyncio.sleep(20)
    await status.delete()


# ================= AUTO WATCHER =================
@app.on_message(filters.group & (filters.photo | filters.sticker | filters.document))
async def auto_nsfw(client: Client, msg: Message):
    if not await get_nsfw_status(msg.chat.id):
        return

    is_nsfw, data, reason = await scan_media(client, msg)

    if is_nsfw and data:
        try:
            await msg.delete()
        except:
            return

        text = (
            f"🚨 **NSFW Content Removed**\n"
            f"👤 User: {msg.from_user.mention}\n"
            f"🔎 Reason: `{reason}`\n\n"
            f"📊 **AI Analysis:**\n"
            f"{format_scores(data.get('scores', {}))}"
        )

        info = await client.send_message(msg.chat.id, text)
        await asyncio.sleep(20)
        await info.delete()


# ================= START =================
app.run()