"""Per-user monthly LLM budget protection backed by Redis when available."""
import time

from fastapi import HTTPException

from app.config import settings
from app.storage import redis_client

_monthly_costs: dict[str, float] = {}


def _month_key(user_id: str) -> str:
    return f"cost:{user_id}:{time.strftime('%Y-%m')}"


def get_monthly_cost(user_id: str) -> float:
    key = _month_key(user_id)
    if redis_client is not None:
        return float(redis_client.get(key) or 0)
    return _monthly_costs.get(key, 0.0)


def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int) -> None:
    cost = (input_tokens / 1000) * 0.00015 + (output_tokens / 1000) * 0.0006
    key = _month_key(user_id)
    if redis_client is not None:
        recorded = redis_client.eval(
            """
            local current = tonumber(redis.call('GET', KEYS[1]) or '0')
            if current + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
                return 0
            end
            redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
            redis.call('EXPIRE', KEYS[1], 2764800)
            return 1
            """,
            1,
            key,
            cost,
            settings.monthly_budget_usd,
        )
        if not recorded:
            raise HTTPException(402, "Monthly budget exhausted.")
        return

    current = _monthly_costs.get(key, 0.0)
    if current + cost > settings.monthly_budget_usd:
        raise HTTPException(402, "Monthly budget exhausted.")
    _monthly_costs[key] = current + cost
