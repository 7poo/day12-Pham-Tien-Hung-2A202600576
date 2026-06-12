"""Redis connection with an in-memory fallback for local development."""
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

redis_client = None
_memory_history: dict[str, list[dict]] = {}
if settings.redis_url:
    try:
        import redis

        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
    except Exception as exc:
        logger.warning("Redis unavailable; using local fallback: %s", exc)
        redis_client = None


def redis_ready() -> bool:
    if redis_client is None:
        return False
    try:
        return bool(redis_client.ping())
    except Exception:
        return False


def get_history(user_id: str) -> list[dict]:
    key = f"history:{user_id}"
    if redis_client is not None:
        return [json.loads(item) for item in redis_client.lrange(key, 0, -1)]
    return list(_memory_history.get(key, []))


def append_history(user_id: str, role: str, content: str) -> list[dict]:
    key = f"history:{user_id}"
    message = {"role": role, "content": content}
    if redis_client is not None:
        pipe = redis_client.pipeline()
        pipe.rpush(key, json.dumps(message))
        pipe.ltrim(key, -20, -1)
        pipe.expire(key, 32 * 24 * 3600)
        pipe.execute()
        return get_history(user_id)
    history = _memory_history.setdefault(key, [])
    history.append(message)
    _memory_history[key] = history[-20:]
    return list(_memory_history[key])
