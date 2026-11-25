import os
from dataclasses import dataclass
from math import isfinite


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return value if isfinite(value) else default
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    port: int = _int("PORT", 8000)
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_api_key: str = os.getenv("AGENT_API_KEY", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    rate_limit_per_minute: int = _int("RATE_LIMIT_PER_MINUTE", 10)
    daily_budget_usd: float = _float("DAILY_BUDGET_USD", 0.0)
    monthly_budget_usd: float = _float("MONTHLY_BUDGET_USD", 10.0)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
