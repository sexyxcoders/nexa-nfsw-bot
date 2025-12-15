import os, time
from motor.motor_asyncio import AsyncIOMotorClient

mongo = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = mongo[os.getenv("DB_NAME", "nexa_nsfw")]

settings = db.settings
cache = db.cache

async def init_db():
    await settings.create_index("chat_id", unique=True)
    await cache.create_index("file_id", unique=True)
    await cache.create_index("created_at", expireAfterSeconds=3600)

async def set_nsfw_status(chat_id: int, state: bool):
    await settings.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": state}},
        upsert=True
    )

async def get_nsfw_status(chat_id: int) -> bool:
    data = await settings.find_one({"chat_id": chat_id})
    return data["enabled"] if data else False

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