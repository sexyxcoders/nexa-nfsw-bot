from pymongo import MongoClient
import os
import time

MONGO_URL = os.getenv("MONGO_URL")

mongo = MongoClient(MONGO_URL)
db = mongo["nexa_nsfw"]

# Collections
groups = db.groups
scan_cache = db.scan_cache

# ===============================
# GROUP NSFW SETTINGS
# ===============================

async def set_nsfw_status(chat_id: int, status: bool):
    groups.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": status}},
        upsert=True
    )


async def get_nsfw_status(chat_id: int) -> bool:
    data = groups.find_one({"chat_id": chat_id})
    return bool(data and data.get("enabled"))


# ===============================
# SCAN CACHE (ANTI-SPAM / SPEED)
# ===============================

CACHE_TTL = 60 * 60 * 24  # 24 hours


async def get_cached_scan(file_unique_id: str):
    doc = scan_cache.find_one({"_id": file_unique_id})
    if not doc:
        return None

    # Expired cache
    if time.time() - doc["time"] > CACHE_TTL:
        scan_cache.delete_one({"_id": file_unique_id})
        return None

    return doc


async def cache_scan_result(file_unique_id: str, safe: bool, data: dict):
    scan_cache.update_one(
        {"_id": file_unique_id},
        {
            "$set": {
                "safe": safe,
                "data": data,
                "time": time.time()
            }
        },
        upsert=True
    )