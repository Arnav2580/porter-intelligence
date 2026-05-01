"""API surface contract tests.

These tests keep production routing explicit. If a route is added, removed, or
archived, update this contract intentionally instead of letting hidden router
imports drift.
"""

from pathlib import Path

from api.main import app
from api.router_registry import LIVE_ROUTERS


EXPECTED_ROUTES = {
    ("GET", "/"),
    ("GET", "/auth/admin/users"),
    ("POST", "/auth/admin/users"),
    ("GET", "/auth/me"),
    ("POST", "/auth/token"),
    ("GET", "/cases"),
    ("GET", "/cases/"),
    ("POST", "/cases/batch-review"),
    ("GET", "/cases/summary/counts"),
    ("GET", "/cases/summary/dashboard"),
    ("GET", "/cases/{case_id}"),
    ("PATCH", "/cases/{case_id}"),
    ("POST", "/cases/{case_id}/driver-action"),
    ("GET", "/cases/{case_id}/history"),
    ("GET", "/demand/forecast/{zone_id}"),
    ("GET", "/demo/preset/{name}"),
    ("POST", "/demo/reset"),
    ("GET", "/demo/scenarios"),
    ("GET", "/efficiency/dead-miles"),
    ("GET", "/efficiency/fleet-zones"),
    ("GET", "/efficiency/reallocation"),
    ("GET", "/efficiency/summary"),
    ("GET", "/efficiency/utilisation/{zone_id}"),
    ("GET", "/fraud/driver/{driver_id}"),
    ("GET", "/fraud/heatmap"),
    ("GET", "/fraud/live-feed"),
    ("POST", "/fraud/score"),
    ("GET", "/fraud/tier-summary"),
    ("GET", "/health"),
    ("POST", "/ingest/batch-csv"),
    ("GET", "/ingest/schema-map/default"),
    ("GET", "/ingest/status"),
    ("POST", "/ingest/trip-completed"),
    ("GET", "/intelligence/driver/{driver_id}"),
    ("GET", "/intelligence/top-risk"),
    ("GET", "/kpi/live"),
    ("GET", "/kpi/report"),
    ("GET", "/kpi/summary"),
    ("GET", "/legal/commercial-schedule"),
    ("GET", "/legal/download"),
    ("GET", "/legal/download/acceptance-criteria"),
    ("GET", "/legal/download/commercial-schedule"),
    ("GET", "/legal/download/nda"),
    ("GET", "/legal/download/support-scope"),
    ("GET", "/legal/term-sheet"),
    ("GET", "/metrics"),
    ("POST", "/query"),
    ("GET", "/reports/board-pack"),
    ("GET", "/reports/daily-summary"),
    ("GET", "/reports/model-performance"),
    ("POST", "/roi/calculate"),
    ("GET", "/roi/summary"),
    ("POST", "/shadow/activate"),
    ("POST", "/shadow/deactivate"),
    ("GET", "/shadow/status"),
    ("POST", "/webhooks/dispatch/test"),
}


def test_live_api_route_contract():
    actual = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith(("/docs", "/openapi", "/redoc")):
            continue
        for method in getattr(route, "methods", set()) or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            actual.add((method, path))

    assert actual == EXPECTED_ROUTES


def test_router_registry_is_single_live_registration_surface():
    assert len(LIVE_ROUTERS) == 13

    routes_dir = Path("api/routes")
    archived_shims = {"fraud.py", "kpi.py", "demand.py"}
    assert archived_shims.isdisjoint(
        {path.name for path in routes_dir.glob("*.py")}
    )
