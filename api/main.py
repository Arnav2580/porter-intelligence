"""
Porter Intelligence Platform — FastAPI Application

App initialisation, middleware, and router registration.
All ML endpoints live in api/inference.py.
All startup state lives in api/state.py.
"""

import os
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from generator.config import API_TITLE, API_VERSION, API_DESCRIPTION
from api.state import app_state, lifespan
from database.connection import AsyncSessionLocal
from database.redis_client import ping_redis

app = FastAPI(
    title       = API_TITLE,
    version     = API_VERSION,
    description = API_DESCRIPTION,
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
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
        except Exception:
            pass
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PrometheusMiddleware)

# Register routers
from api.inference import router as inference_router
from api.routes.auth import router as auth_router
from api.routes.cases import router as cases_router
from api.routes.query import router as query_router
from api.routes.driver_intelligence import router as intelligence_router
from api.routes.reports import router as reports_router
from api.routes.route_efficiency import router as efficiency_router
from ingestion.webhook import router as ingest_router

app.include_router(inference_router)
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(query_router)
app.include_router(intelligence_router)
app.include_router(reports_router)
app.include_router(efficiency_router)
app.include_router(ingest_router)


# -- Core endpoints --

DASHBOARD_PATH = Path(__file__).parent.parent / "dashboard" / "index.html"


@app.get("/")
async def root():
    """Serve the dashboard."""
    if DASHBOARD_PATH.exists():
        return FileResponse(DASHBOARD_PATH, media_type="text/html")
    return {"message": "Porter Intelligence Platform", "docs": "/docs"}


@app.post("/webhooks/dispatch/test")
async def test_dispatch():
    """
    Test the enforcement dispatch connection.
    Porter uses this to verify their system
    is receiving alerts correctly.
    """
    from enforcement.dispatch import notify_dispatch
    from auth.dependencies import require_permission
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
    """Prometheus metrics scrape endpoint (Phase C)."""
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
    """Health check endpoint."""
    db_ok = False
    redis_ok = False

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
        db_ok = True
    except Exception:
        pass

    redis_ok = await ping_redis()

    return {
        "status":       "ok" if db_ok else "degraded",
        "model_loaded": app_state.get("model") is not None,
        "trips_loaded": len(app_state.get("trips_df", [])),
        "database":     "ok" if db_ok else "unavailable",
        "redis":        "ok" if redis_ok else "unavailable",
        "threshold":    app_state.get("threshold", 0.45),
        "timestamp":    datetime.now().isoformat(),
        "platform":     "Porter Intelligence Platform",
        "version":      API_VERSION,
    }
