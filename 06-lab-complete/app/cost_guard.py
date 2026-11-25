from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis_client

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

# Check both periods before charging either, even when workers finish together.
CHARGE_BUDGET = """
local cost = tonumber(ARGV[1])
for idx, key in ipairs(KEYS) do
    local total = tonumber(redis.call('GET', key) or '0')
    local limit = tonumber(ARGV[2 * idx])
    if total + cost > limit then
        return 0
    end
end
for idx, key in ipairs(KEYS) do
    redis.call('INCRBYFLOAT', key, ARGV[1])
    redis.call('EXPIRE', key, ARGV[2 * idx + 1])
end
return 1
"""


def _periods() -> list[tuple[str, float, int]]:
    now = datetime.now(timezone.utc)
    periods = [(f"cost:monthly:{now:%Y-%m}", settings.monthly_budget_usd, 32 * 86400)]
    if settings.daily_budget_usd > 0:
        periods.append((f"cost:daily:{now:%Y-%m-%d}", settings.daily_budget_usd, 2 * 86400))
    return periods


def check_budget() -> None:
    periods = _periods()
    totals = get_redis_client().mget([key for key, _, _ in periods])
    if any(float(total or 0) >= limit for total, (_, limit, _) in zip(totals, periods)):
        raise HTTPException(status_code=402, detail="Budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> None:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    periods = _periods()
    keys = [key for key, _, _ in periods]
    limits_and_expirations = [value for _, limit, ttl in periods for value in (limit, ttl)]
    charged = get_redis_client().eval(
        CHARGE_BUDGET, len(keys), *keys, f"{cost:.8f}", *limits_and_expirations
    )
    if not charged:
        raise HTTPException(status_code=402, detail="Budget exceeded")
