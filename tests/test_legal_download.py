"""Tests for /legal/download close packet endpoints."""

import os
import zipfile
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.legal import router as legal_router
from auth.dependencies import get_current_user, require_permission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(role: str = "admin") -> FastAPI:
    """Build a minimal FastAPI app with the legal router, injecting a fake user."""
    app = FastAPI()
    app.include_router(legal_router)

    fake_user = {"sub": "testuser", "role": role}

    def _fake_user():
        return fake_user

    # Override the dependency that get_current_user injects
    app.dependency_overrides[get_current_user] = _fake_user
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_download_close_packet_zip(security_env):
    """GET /legal/download returns a valid ZIP with 4 PDFs."""
    app = _make_app(role="admin")
    with TestClient(app) as client:
        resp = client.get("/legal/download")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "porter-intelligence-close-packet" in resp.headers["content-disposition"]

    zf = zipfile.ZipFile(BytesIO(resp.content))
    names = zf.namelist()
    assert "NDA.pdf" in names
    assert "Commercial-Schedule.pdf" in names
    assert "Acceptance-Criteria.pdf" in names
    assert "Deployment-and-Support-Scope.pdf" in names

    # Each PDF must start with the PDF magic bytes
    for name in names:
        assert zf.read(name)[:4] == b"%PDF", f"{name} is not a valid PDF"


def test_download_nda_pdf(security_env):
    app = _make_app(role="admin")
    with TestClient(app) as client:
        resp = client.get("/legal/download/nda")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert 'filename="NDA.pdf"' in resp.headers["content-disposition"]


def test_download_commercial_schedule_pdf(security_env):
    app = _make_app(role="admin")
    with TestClient(app) as client:
        resp = client.get("/legal/download/commercial-schedule")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_download_acceptance_criteria_pdf(security_env):
    app = _make_app(role="admin")
    with TestClient(app) as client:
        resp = client.get("/legal/download/acceptance-criteria")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_download_support_scope_pdf(security_env):
    app = _make_app(role="admin")
    with TestClient(app) as client:
        resp = client.get("/legal/download/support-scope")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_legal_download_requires_auth():
    """Unauthenticated request (no override) must be rejected with 403/401."""
    app = FastAPI()
    app.include_router(legal_router)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/legal/download")
    assert resp.status_code in (401, 403, 422)


def test_legal_download_analyst_forbidden(security_env):
    """ops_analyst must not be able to download the close packet (lacks read:all)."""
    # analyst role does not have read:all — require_permission("read:all") will 403
    # We test this with the real auth dependency (no override)
    from fastapi.testclient import TestClient as TC
    from auth.jwt import create_access_token

    app = FastAPI()
    app.include_router(legal_router)

    analyst_token = create_access_token(
        data={"sub": "analyst_1", "role": "ops_analyst"}
    )
    with TC(app) as client:
        resp = client.get(
            "/legal/download",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
    assert resp.status_code in (401, 403)
