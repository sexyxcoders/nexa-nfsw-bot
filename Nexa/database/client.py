import time
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]

settings = db.settings
cache = db.cache
users = db.users
groups = db.groups


def init_db():
    settings.create_index("chat_id", unique=True)
    cache.create_index("file_id", unique=True)
    cache.create_index("created_at", expireAfterSeconds=3600)
    users.create_index([("chat_id", 1), ("user_id", 1)], unique=True)
    groups.create_index("chat_id", unique=True)


def set_nsfw_status(chat_id: int, state: bool):
    settings.update_one(
        {"chat_id": chat_id},
        {"$set": {"enabled": state}},
        upsert=True
    )


def get_nsfw_status(chat_id: int) -> bool:
    d = settings.find_one({"chat_id": chat_id})
    return d["enabled"] if d else False


def get_cached_scan(file_id: str):
    return cache.find_one({"file_id": file_id})


def cache_scan_result(file_id: str, safe: bool, data: dict):
    cache.update_one(
        {"file_id": file_id},
        {"$set": {
            "safe": safe,
            "data": data,
            "created_at": time.time()
        }},
        upsert=True
    )


def get_global_stats():
    total_users = len(users.distinct("user_id"))
    total_chats = groups.count_documents({})
    return {"users": total_users, "chats": total_chats}