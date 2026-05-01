"""Single source of truth for FastAPI router registration.

Only routers in LIVE_ROUTERS are part of the deployed API surface. Legacy
compatibility shims that do not register routes belong in _archive.
"""

from fastapi import FastAPI

from api.inference import router as inference_router
from api.routes.auth import router as auth_router
from api.routes.cases import router as cases_router
from api.routes.demo import router as demo_router
from api.routes.driver_intelligence import router as intelligence_router
from api.routes.legal import router as legal_router
from api.routes.live_kpi import router as live_kpi_router
from api.routes.query import router as query_router
from api.routes.reports import router as reports_router
from api.routes.roi import router as roi_router
from api.routes.route_efficiency import router as efficiency_router
from api.routes.shadow import router as shadow_router
from ingestion.webhook import router as ingest_router


LIVE_ROUTERS = (
    inference_router,
    auth_router,
    cases_router,
    query_router,
    intelligence_router,
    demo_router,
    reports_router,
    roi_router,
    efficiency_router,
    shadow_router,
    live_kpi_router,
    legal_router,
    ingest_router,
)


def register_routers(app: FastAPI) -> None:
    """Attach all deployed routers to the FastAPI app."""
    for router in LIVE_ROUTERS:
        app.include_router(router)
