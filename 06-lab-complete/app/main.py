import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import close_redis, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        for key in ("method", "path", "status", "ms"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


logger = logging.getLogger("agent")
_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logger.addHandler(_handler)
logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")
    try:
        yield
    finally:
        close_redis()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, error: RedisError):
    logger.warning("redis_unavailable", extra={"path": request.url.path})
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"status": "ready"}


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round(elapsed_ms, 2),
        },
    )
    return response


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question.split()))
    output_tokens = max(1, len(answer.split()))
    record_cost(input_tokens, output_tokens)
    return {"question": body.question, "answer": answer}
