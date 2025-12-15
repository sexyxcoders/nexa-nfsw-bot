import time
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

# ─── DATABASE CONNECTION ──────────────────────────────────
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]

# ─── COLLECTIONS ──────────────────────────────────────────
settings = db.settings          # NSFW ON/OFF per group
cache = db.cache                # Scan cache
users = db.users                # Users stats
groups = db.groups              # Group stats


# ─── INIT DB (INDEXES) ────────────────────────────────────
async def init_db():
    await settings.create_index("chat_id", unique=True)

    await cache.create_index("file_id", unique=True)
    await cache.create_index("created_at", expireAfterSeconds=3600)

    await users.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
    await groups.create_index("chat_id", unique=True)


# ─── NSFW SETTINGS ────────────────────────────────────────
async def set_nsfw_status(chat_id: int, state: bool):
    await settings.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": state}},
        upsert=True
    )

async def get_nsfw_status(chat_id: int) -> bool:
    d = await settings.find_one({"chat_id": chat_id})
    return d["enabled"] if d else False


# ─── SCAN CACHE ───────────────────────────────────────────
async def get_cached_scan(file_id: str):
    return await cache.find_one({"file_id": file_id})

async def cache_scan_result(file_id: str, safe: bool, data: dict):
    await cache.update_one(
        {"file_id": file_id},
        {"$set": {
            "safe": safe,
            "data": data,
            "created_at": time.time()
        }},
        upsert=True
    )


# ─── USER & GROUP STATS (FOR /stats) ──────────────────────
async def inc_user(chat_id: int, user_id: int):
    await users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"media": 1}},
        upsert=True
    )

async def inc_user_nsfw(chat_id: int, user_id: int):
    await users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"nsfw": 1}},
        upsert=True
    )

async def inc_group_scan(chat_id: int):
    await groups.update_one(
        {"chat_id": chat_id},
        {"$inc": {"scans": 1}},
        upsert=True
    )

async def inc_group_nsfw(chat_id: int):
    await groups.update_one(
        {"chat_id": chat_id},
        {"$inc": {"nsfw": 1}},
        upsert=True
    )


# ─── GLOBAL STATS (NEXA STATS) ─────────────────────────────
async def get_global_stats():
    total_users = await users.distinct("user_id")
    total_chats = await groups.count_documents({})
    return {
        "users": len(total_users),
        "chats": total_chats
    }