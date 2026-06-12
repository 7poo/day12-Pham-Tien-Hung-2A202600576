"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting
  ✅ Cost guard
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import os
import time
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.cost_guard import check_and_record_cost, get_monthly_cost
from app.rate_limiter import check_rate_limit
from app.storage import append_history, get_history, redis_ready
from app.ui import UI_HTML

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Shared rate limiter
# ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────
# Shared cost guard
# ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str
    conversation_turn: int

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["Info"])
def root():
    return UI_HTML


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    # Rate limit per API key
    check_rate_limit(body.user_id)

    # Budget check
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(body.user_id, input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    history = get_history(body.user_id)
    previous_questions = [item["content"] for item in history if item["role"] == "user"]
    if "what did i just say" in body.question.lower() and previous_questions:
        answer = f'Your previous message was: "{previous_questions[-1]}"'
    else:
        answer = llm_ask(body.question)

    output_tokens = len(answer.split()) * 2
    check_and_record_cost(body.user_id, 0, output_tokens)
    append_history(body.user_id, "user", body.question)
    updated_history = append_history(body.user_id, "assistant", answer)

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        conversation_turn=len([item for item in updated_history if item["role"] == "user"]),
    )


@app.get("/history/{user_id}", tags=["Agent"])
def history(user_id: str, _key: str = Depends(verify_api_key)):
    """Return Redis-backed conversation history for a user."""
    return {"user_id": user_id, "messages": get_history(user_id)}


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"llm": "mock" if not settings.openai_api_key else "openai"}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if settings.redis_url and not redis_ready():
        raise HTTPException(503, "Redis not ready")
    return {"ready": True, "redis_connected": redis_ready()}


@app.get("/metrics", tags=["Operations"])
def metrics(user_id: str = "default", _key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    monthly_cost = get_monthly_cost(user_id)
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "user_id": user_id,
        "monthly_cost_usd": round(monthly_cost, 4),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "budget_used_pct": round(monthly_cost / settings.monthly_budget_usd * 100, 1),
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
