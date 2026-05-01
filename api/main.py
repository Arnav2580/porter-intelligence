"""
Porter Intelligence Platform — FastAPI Application

App initialisation, middleware, and router registration.
All ML endpoints live in api/inference.py.
All startup state lives in api/state.py.
"""

import logging
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

from api.limiting import limiter
from api.router_registry import register_routers
from generator.config import API_TITLE, API_VERSION, API_DESCRIPTION
from api.state import app_state, lifespan
from database.connection import AsyncSessionLocal
from database.redis_client import ping_redis
from runtime_config import describe_data_provenance
from security.settings import get_allowed_origins

logger = logging.getLogger(__name__)

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    redirect_slashes=False,
    openapi_tags=[
        {
            "name": "platform",
            "description": "Scoring, evaluation, and core operating endpoints.",
        },
        {
            "name": "auth",
            "description": "Authentication and operator identity endpoints.",
        },
        {
            "name": "cases",
            "description": "Case review, queue management, and audit-backed workflow endpoints.",
        },
        {
            "name": "reports",
            "description": "Management reporting built from reviewed operational outcomes.",
        },
        {
            "name": "intelligence",
            "description": "Driver risk and network intelligence endpoints.",
        },
        {
            "name": "route_efficiency",
            "description": "Fleet efficiency and reallocation insight endpoints.",
        },
        {
            "name": "query",
            "description": "Natural-language operations query endpoint.",
        },
        {
            "name": "ingestion",
            "description": "Data ingestion, mapping, and queue status endpoints.",
        },
        {
            "name": "shadow",
            "description": "Shadow-mode status and safety boundaries.",
        },
        {
            "name": "kpi",
            "description": "Reviewed-case KPI surfaces for live operating visibility.",
        },
        {
            "name": "roi",
            "description": "Commercial savings, payback, and ROI planning endpoints.",
        },
        {
            "name": "demo",
            "description": "Demo-control endpoints for rehearsal, presets, and safe reset flows.",
        },
    ],
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = get_allowed_origins(),
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Track HTTP request latency per endpoint (Phase C)."""
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        try:
            from monitoring.metrics import HTTP_REQUEST_LATENCY
            HTTP_REQUEST_LATENCY.labels(
                method   = request.method,
                endpoint = request.url.path,
                status   = str(response.status_code),
            ).observe(duration)
        except Exception as exc:
            logger.debug("Prometheus latency metric skipped: %s", exc)
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PrometheusMiddleware)
register_routers(app)


@app.get("/")
async def root():
    """API landing endpoint.

    The production dashboard is the React app in dashboard-ui/. The backend
    root intentionally returns API metadata instead of serving a legacy static
    dashboard from the old dashboard/ directory.
    """
    return {
        "message": "Porter Intelligence Platform API",
        "docs": "/docs",
        "health": "/health",
    }


from auth.dependencies import require_permission as _require_permission


@app.post("/webhooks/dispatch/test")
async def test_dispatch(
    _user=Depends(_require_permission("write:all")),
):
    """
    Test the downstream dispatch connection safely. Admin only.
    """
    from enforcement.dispatch import notify_dispatch
    result = await notify_dispatch(
        driver_id         = "TEST_DRIVER_001",
        trip_id           = "TEST_TRIP_001",
        fraud_probability = 0.999,
        tier              = "action",
        top_signals       = [
            "Test alert — connectivity verification",
        ],
        action            = "test",
    )
    return {
        "test_status":         "ok",
        "dispatch_result":     result,
        "dispatch_configured": bool(os.getenv("PORTER_DISPATCH_URL")),
    }


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics scrape endpoint."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
    except ImportError:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain",
        )


@app.get("/health")
async def health():
    """Health, runtime-mode, and dependency readiness endpoint."""
    db_ok = False
    redis_ok = False
    runtime_mode = app_state.get("runtime_mode", "prod")
    synthetic_feed_enabled = app_state.get(
        "synthetic_feed_enabled",
        False,
    )
    shadow_mode = app_state.get("shadow_mode", False)

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
        db_ok = True
    except Exception as exc:
        logger.debug("Health-check DB probe failed: %s", exc)

    redis_ok = await ping_redis()

    return {
        "status":       "ok" if db_ok else "degraded",
        "model_loaded": app_state.get("model") is not None,
        "trips_loaded": len(app_state.get("trips_df", [])),
        "database":     "ok" if db_ok else "unavailable",
        "redis":        "ok" if redis_ok else "unavailable",
        "runtime_mode": runtime_mode,
        "synthetic_feed_enabled": synthetic_feed_enabled,
        "data_provenance": describe_data_provenance(
            runtime_mode,
            synthetic_feed_enabled,
            shadow_mode,
        ),
        "shadow_mode": shadow_mode,
        "security_ready": app_state.get(
            "security_validation",
            {},
        ).get("ready", False),
        "security_warnings": app_state.get(
            "security_validation",
            {},
        ).get("warnings", []),
        "thresholds": {
            "watchlist_threshold": (
                app_state.get("two_stage_config") or {}
            ).get("watchlist_threshold", 0.50),
            "action_threshold": (
                app_state.get("two_stage_config") or {}
            ).get("action_threshold", 0.80),
        },
        "simulator_summary": app_state.get(
            "simulator_summary"
        ),
        "timestamp":    datetime.now().isoformat(),
        "platform":     "Porter Intelligence Platform",
        "version":      API_VERSION,
    }
