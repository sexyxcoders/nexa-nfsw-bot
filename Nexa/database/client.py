from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
nsfw_col = db.nsfw


async def get_nsfw_status(chat_id: int) -> bool:
    data = await nsfw_col.find_one({"_id": chat_id})
    return bool(data and data.get("enabled", False))


async def set_nsfw_status(chat_id: int, state: bool):
    await nsfw_col.update_one(
        {"_id": chat_id},
        {"$set": {"enabled": state}},
        upsert=True
    )


async def get_cached_scan(file_id: str):
    return await db.scans.find_one({"_id": file_id})


async def cache_scan_result(file_id: str, safe: bool, data: dict):
    await db.scans.update_one(
        {"_id": file_id},
        {"$set": {"safe": safe, "data": data}},
        upsert=True
    )