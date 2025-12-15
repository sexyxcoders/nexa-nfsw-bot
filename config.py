import os

# ───────────────── TELEGRAM CONFIG ─────────────────
API_ID = int(os.getenv("API_ID", "22657083"))
API_HASH = os.getenv("API_HASH", "d6186691704bd901bdab275ceaab88f3")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ───────────────── DATABASE CONFIG ──────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://pikachuxivan_db_user:pikachuxivan@cluster0.9c3hko7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "nexa_nsfw")

# ───────────────── REDIS CONFIG ─────────────────────
# ⚠️ MUST be pure redis:// URL (no redis-cli)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_TTL = int(os.getenv("REDIS_TTL", "3600"))  # 1 hour

# ───────────────── NSFW API CONFIG ──────────────────
NSFW_API_URL = os.getenv(
    "NSFW_API_URL",
    "https://nexacoders-nexa-api.hf.space/scan"
)

# ───────────────── NSFW THRESHOLD ───────────────────
NSFW_THRESHOLD = float(os.getenv("NSFW_THRESHOLD", "0.02"))

# ───────────────── IMAGE OPTIMIZATION ───────────────
IMAGE_MAX_SIZE = int(os.getenv("IMAGE_MAX_SIZE", "256"))
IMAGE_MIN_BYTES = int(os.getenv("IMAGE_MIN_BYTES", "40960"))

# ───────────────── LOG SETTINGS ─────────────────────
LOG_DELETE_TIME = int(os.getenv("LOG_DELETE_TIME", "15"))

# ───────────────── PERFORMANCE ──────────────────────
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))