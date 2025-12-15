import json
import redis
from config import REDIS_URL, REDIS_TTL

rdb = redis.from_url(REDIS_URL, decode_responses=True)

def redis_get(key):
    v = rdb.get(key)
    return json.loads(v) if v else None

def redis_set(key, value):
    rdb.setex(key, REDIS_TTL, json.dumps(value))