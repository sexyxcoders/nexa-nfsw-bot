import os
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URL"))
db = client["simple_nsfw_bot"]

groups = db["groups"]
groups.create_index("chat_id", unique=True)

print("✅ MongoDB connected")