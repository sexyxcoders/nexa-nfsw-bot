import os

# ───────────────── TELEGRAM CONFIG ─────────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ───────────────── DATABASE CONFIG ──────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://pikachuxivan_db_user:pikachuxivan@cluster0.9c3hko7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "nexa_nsfw")

# ───────────────── REDIS CONFIG ─────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis-cli -u redis://default:EoVeOmg0umOEOElJhkJaM1k4slrIQeag@redis-19314.c232.us-east-1-2.ec2.cloud.redislabs.com:19314")
REDIS_TTL = int(os.getenv("REDIS_TTL", "3600"))  # 1 hour

# ───────────────── NSFW API CONFIG ──────────────────
NSFW_API_URL = os.getenv(
    "NSFW_API_URL",
    "https://nexacoders-nexa-api.hf.space/scan"
)

# ───────────────── NSFW THRESHOLD ───────────────────
# 2% rule (porn / hentai / sexy)
NSFW_THRESHOLD = float(os.getenv("NSFW_THRESHOLD", "0.02"))

# ───────────────── IMAGE OPTIMIZATION ───────────────
IMAGE_MAX_SIZE = int(os.getenv("IMAGE_MAX_SIZE", "256"))  # px
IMAGE_MIN_BYTES = int(os.getenv("IMAGE_MIN_BYTES", "40960"))  # 40KB

# ───────────────── LOG SETTINGS ─────────────────────
LOG_DELETE_TIME = int(os.getenv("LOG_DELETE_TIME", "15"))  # seconds

# ───────────────── PERFORMANCE ──────────────────────
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "5"))  # seconds