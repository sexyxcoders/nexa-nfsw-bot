import os
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# ---------------- CONFIG ----------------
MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    raise RuntimeError("❌ MONGO_URL environment variable not set")

# ---------------- CONNECT ----------------
try:
    client = MongoClient(
        MONGO_URL,
        serverSelectionTimeoutMS=5000
    )
    # Force connection test
    client.admin.command("ping")
except ServerSelectionTimeoutError:
    raise RuntimeError("❌ Could not connect to MongoDB")

# ---------------- DATABASE ----------------
db = client["nexa_nsfw_bot"]

# ---------------- COLLECTIONS ----------------
groups = db["groups"]   # group settings (enable/disable)
users = db["users"]     # user warnings per group
stats = db["stats"]     # usage stats (optional)

# ---------------- INDEXES ----------------
groups.create_index("chat_id", unique=True)
users.create_index([("chat_id", 1), ("user_id", 1)], unique=True)

print("✅ MongoDB connected successfully")
