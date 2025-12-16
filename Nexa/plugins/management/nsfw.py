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

logger = logging.getLogger(__name__)

NSFW_API_URL = "https://nexacoders-nexa-api.hf.space/batch-scan"

# =====================================================
# GLOBAL SESSION
# =====================================================

_ai_session: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    global _ai_session
    if _ai_session is None or _ai_session.closed:
        _ai_session = aiohttp.ClientSession()
    return _ai_session


# =====================================================
# IMAGE OPTIMIZATION
# =====================================================

def optimize_image(image_bytes: bytes) -> bytes:
    """
    Ultra-fast optimization for NSFW AI
    """
    if len(image_bytes) < 50 * 1024:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((256, 256))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=80)
        return out.getvalue()
    except Exception:
        return image_bytes


# =====================================================
# UI FORMATTING
# =====================================================

def format_scores_ui(scores: dict) -> str:
    icons = {
        "porn": "🔞",
        "hentai": "👾",
        "sexy": "💋",
        "neutral": "😐",
        "drawings": "🎨",
    }

    lines = []
    for label, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        icon = icons.get(label, "🔸")
        lines.append(f"{icon} `{label.title():<10} : {score*100:05.2f}%`")

    return "\n".join(lines)


# =====================================================
# 1️⃣ NSFW SETTINGS COMMAND
# =====================================================

@Client.on_message(filters.command("nsfw") & filters.group)
@AdminRights
async def nsfw_toggle_command(client: Client, message: Message):

    if len(message.command) < 2:
        status = await get_nsfw_status(message.chat.id)
        state = "Enabled" if status else "Disabled"
        await message.reply_text(
            f"🚀 **NSFW System:** `{state}`\n"
            f"Usage: `/nsfw on` or `/nsfw off`"
        )
        return

    action = message.command[1].lower()

    if action in ("on", "enable", "true"):
        await set_nsfw_status(message.chat.id, True)
        await message.reply_text("🚀 **NSFW Enabled** — Hyper-Speed Scanning ON")

    elif action in ("off", "disable", "false"):
        await set_nsfw_status(message.chat.id, False)
        await message.reply_text("💤 **NSFW Disabled**")

    else:
        await message.reply_text("❌ Use `/nsfw on` or `/nsfw off`")


# =====================================================
# 2️⃣ MANUAL SCAN
# =====================================================

@Client.on_message(filters.command("scan"))
async def manual_scan_command(client: Client, message: Message):

    if not message.reply_to_message:
        await message.reply_text("⚠️ Reply to an image/sticker.")
        return

    status_msg = await message.reply_text("⚡ **Scanning…**")

    start = time.time()
    is_nsfw, data, reason = await process_media_scan(
        client, message.reply_to_message, manual_override=True
    )
    elapsed = time.time() - start

    if not data:
        await status_msg.edit_text("❌ Scan failed.")
        return

    header = "🚨 **UNSAFE**" if is_nsfw else "✅ **SAFE**"
    bar = "🟥" * 12 if is_nsfw else "🟩" * 12

    await status_msg.edit_text(
        f"{header}\n"
        f"⏱️ `{elapsed:.2f}s`\n"
        f"🔎 `{reason}`\n"
        f"{bar}\n\n"
        f"📊 **Scores:**\n"
        f"{format_scores_ui(data.get('scores', {}))}"
    )


# =====================================================
# 3️⃣ AUTO WATCHER
# =====================================================

@Client.on_message(filters.group & (filters.photo | filters.sticker | filters.document), group=5)
async def nsfw_watcher(client: Client, message: Message):

    if not await get_nsfw_status(message.chat.id):
        return

    is_nsfw, data, reason = await process_media_scan(client, message)

    if is_nsfw and data:
        await handle_nsfw_detection(client, message, data, reason)


# =====================================================
# 4️⃣ CORE ENGINE
# =====================================================

def check_strict_nsfw(scores: dict) -> tuple[bool, str]:
    porn = scores.get("porn", 0)
    hentai = scores.get("hentai", 0)
    sexy = scores.get("sexy", 0)

    if porn > 0.08:
        return True, f"Porn ({porn*100:.0f}%)"
    if hentai > 0.15:
        return True, f"Hentai ({hentai*100:.0f}%)"
    if sexy > 0.45:
        return True, f"Sexy ({sexy*100:.0f}%)"
    if porn + hentai + sexy > 0.40:
        return True, "High-Risk Mix"

    return False, "Safe"


async def process_media_scan(
    client: Client,
    message: Message,
    manual_override: bool = False
):
    media = None
    file_uid = None
    use_thumb = False

    if message.sticker:
        media = message.sticker
        file_uid = media.file_unique_id
        if media.is_animated or media.is_video:
            use_thumb = True
            if not media.thumbs:
                return False, None, "No thumbnail"

    elif message.photo:
        media = message.photo
        file_uid = media.file_unique_id

    elif message.document and message.document.mime_type and "image" in message.document.mime_type:
        media = message.document
        file_uid = media.file_unique_id

    if not file_uid:
        return False, None, "Invalid media"

    if not manual_override:
        cached = await get_cached_scan(file_uid)
        if cached:
            ok, reason = check_strict_nsfw(cached["data"]["scores"])
            return ok, cached["data"], reason

    try:
        if hasattr(media, "file_size") and media.file_size > 10 * 1024 * 1024:
            return False, None, "File too large"

        stream = (
            await client.download_media(media.thumbs[-1].file_id, in_memory=True)
            if use_thumb else
            await client.download_media(message, in_memory=True)
        )

        image_bytes = optimize_image(bytes(stream.getbuffer()))

    except Exception:
        return False, None, "Download error"

    try:
        session = await get_session()
        form = aiohttp.FormData()
        form.add_field("file", image_bytes, filename="scan.jpg")

        async with session.post(NSFW_API_URL, data=form, timeout=6) as r:
            if r.status != 200:
                return False, None, "API error"
            data = await r.json()

    except Exception:
        return False, None, "Connection error"

    is_nsfw, reason = check_strict_nsfw(data.get("scores", {}))
    await cache_scan_result(file_uid, not is_nsfw, data)

    return is_nsfw, data, reason


async def handle_nsfw_detection(client: Client, message: Message, data: dict, reason: str):
    try:
        await message.delete()

        msg = await client.send_message(
            message.chat.id,
            f"🔔 **NSFW Removed**\n"
            f"👤 {message.from_user.mention}\n"
            f"🚨 `{reason}`\n\n"
            f"{format_scores_ui(data.get('scores', {}))}"
        )

        await asyncio.sleep(15)
        await msg.delete()

    except Exception:
        pass