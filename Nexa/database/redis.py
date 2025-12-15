import os, redis, json

redis_db = redis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True
)

def redis_get(key):
    v = redis_db.get(key)
    return json.loads(v) if v else None

def redis_set(key, value, ttl=3600):
    redis_db.setex(key, ttl, json.dumps(value))