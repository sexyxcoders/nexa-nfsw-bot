import os
import logging
import asyncio
import aiohttp
import io
import time
import tempfile
import subprocess
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NexaNSFW")

# =====================================================
# HTTP SESSION
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
# FAST SAFE SKIP
# =====================================================
def fast_safe(msg: Message) -> bool:
    try:
        if msg.photo and msg.photo.file_size and msg.photo.file_size < 40_000:
            return True
        if msg.sticker and msg.sticker.file_size and msg.sticker.file_size < 30_000:
            return True
    except:
        pass
    return False

# =====================================================
# IMAGE OPTIMIZATION
# =====================================================
def optimize_image(raw: bytes) -> bytes:
    if len(raw) < 50 * 1024:
        return raw
    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        img.thumbnail((160, 160))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=75)
        return buf.getvalue()
    except:
        return raw

# =====================================================
# SCORE FORMATTER (NEW)
# =====================================================
def format_scores(scores: dict) -> str:
    icons = {
        "porn": "🔞",
        "neutral": "😐",
        "sexy": "💋",
        "drawings": "🎨",
        "hentai": "👾",
    }
    lines = []
    for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{icons.get(k,'🔹')} {k.title():10} : {v*100:05.2f}%")
    return "\n".join(lines)

# =====================================================
# NSFW DECISION (2% RULE)
# =====================================================
def strict_nsfw(scores: dict):
    porn = scores.get("porn", 0)
    hentai = scores.get("hentai", 0)

    if porn >= 0.02:
        return True, "Pornographic Content"
    if hentai >= 0.02:
        return True, "Hentai Content"

    return False, "Safe"

# =====================================================
# API CALLER
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
    except:
        pass

    try:
        return await _call(FALLBACK_NSFW_API)
    except:
        pass

    return None

# =====================================================
# VIDEO FRAME EXTRACT
# =====================================================
def extract_video_frames(video_path: str, every_n: int = 15) -> list[str]:
    frames_dir = tempfile.mkdtemp()
    out_pattern = os.path.join(frames_dir, "frame_%03d.jpg")

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"select=not(mod(n\\,{every_n}))",
            "-vsync", "vfr",
            "-q:v", "5",
            out_pattern
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return [os.path.join(frames_dir, f) for f in os.listdir(frames_dir)]

# =====================================================
# CORE SCANNER
# =====================================================
async def scan_media(client: Client, msg: Message, manual=False):
    if not manual and fast_safe(msg):
        return False, None, "Fast-Safe"

    # ---------- VIDEO ----------
    if msg.video or msg.animation:
        path = await client.download_media(msg.video or msg.animation)

        for frame in extract_video_frames(path):
            with open(frame, "rb") as f:
                img = optimize_image(f.read())
            data = await call_nsfw_api(img)
            if not data:
                continue
            verdict, reason = strict_nsfw(data["scores"])
            if verdict:
                return True, data, reason

        return False, None, "Video Safe"

    # ---------- IMAGE ----------
    media = msg.photo or msg.sticker or msg.document
    file_uid = media.file_unique_id

    cached = await get_cached_scan(file_uid)
    if cached and not manual:
        verdict, reason = strict_nsfw(cached["data"]["scores"])
        return verdict, cached["data"], reason

    mem = await client.download_media(msg, in_memory=True)
    img = optimize_image(bytes(mem.getbuffer()))

    data = await call_nsfw_api(img)
    if not data:
        return False, None, "API Error"

    verdict, reason = strict_nsfw(data["scores"])
    await cache_scan_result(file_uid, not verdict, data)
    return verdict, data, reason

# =====================================================
# PYROGRAM CLIENT
# =====================================================
app = Client("nexa_nsfw_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# =====================================================
# AUTO WATCHER
# =====================================================
@app.on_message(filters.group & (filters.photo | filters.sticker | filters.document | filters.video | filters.animation))
async def auto_nsfw(client: Client, msg: Message):
    if not await get_nsfw_status(msg.chat.id):
        return

    async def worker():
        verdict, data, reason = await scan_media(client, msg)
        if not verdict:
            return

        await msg.delete()

        text = (
            "🚨 **NSFW Removed**\n"
            f"👤 {msg.from_user.mention}\n"
            f"🔎 {reason}\n\n"
            f"{format_scores(data['scores'])}"
        )

        notice = await client.send_message(msg.chat.id, text)
        await asyncio.sleep(20)
        await notice.delete()

    asyncio.create_task(worker())

# =====================================================
# STARTUP
# =====================================================
logger.info("🤖 Nexa NSFW Bot Loaded (Ultra Fast + Video Scan)")
app.run()