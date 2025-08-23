from __future__ import annotations
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, BaseSettings, Field

from nav_insights.core.rules import evaluate_rules
from nav_insights.core.actions import Action
from nav_insights.core.insight import Insight
from nav_insights.core.writer import compose_insight_json


class ServiceSettings(BaseSettings):
    rules_path: Optional[str] = None
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    max_request_bytes: int = 10_000_000
    rate_limit_per_minute: int = 60
    writer_base_url: str = "http://localhost:8000/v1"
    writer_model: str = "local"
    writer_timeout: int = 120

    class Config:
        env_prefix = "NI_"
        case_sensitive = False


settings = ServiceSettings()
app = FastAPI(title="nav_insights", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    max_age=600,
)

DEFAULT_RULES = Path(settings.rules_path) if settings.rules_path else (Path(__file__).parent / "domains" / "paid_search" / "rules" / "default.yaml")

# Simple request size limit
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > settings.max_request_bytes:
                raise HTTPException(status_code=413, detail="Request too large")
        except ValueError:
            pass
    return await call_next(request)

# Simple in-memory rate limiting (per-IP, sliding window 60s)
_rate_buckets: dict[str, deque] = defaultdict(deque)

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    bucket = _rate_buckets[client]
    now = time.monotonic()
    window = 60.0
    # drop stale
    while bucket and (now - bucket[0]) > window:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)
    return await call_next(request)


class ActionsRequest(BaseModel):
    ir: dict
    rules_path: Optional[str] = None


@app.post("/v1/actions:evaluate")
async def actions_evaluate(req: ActionsRequest):
    rules_path = req.rules_path or str(DEFAULT_RULES)
    actions = evaluate_rules(req.ir, rules_path)
    return [a.model_dump() for a in actions]


class InsightsRequest(BaseModel):
    ir: dict
    actions: Optional[List[dict]] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@app.post("/v1/insights:compose")
async def insights_compose(req: InsightsRequest):
    rules_path = str(DEFAULT_RULES)
    actions = [Action(**a) for a in req.actions] if req.actions else evaluate_rules(req.ir, rules_path)
    base_url = req.base_url or settings.writer_base_url
    model = req.model or settings.writer_model
    # Compose via thread to avoid blocking the event loop
    try:
        import anyio
        insight = await anyio.to_thread.run_sync(
            compose_insight_json,
            req.ir,
            actions,
            Insight,
            base_url,
            model,
            settings.writer_timeout,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Writer error: {e}")
    return json.loads(insight.model_dump_json())
