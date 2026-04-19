"""Shadow status API tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.shadow import router as shadow_router
from auth.dependencies import get_current_user
from database.connection import get_db


async def _fake_admin_user():
    return {"sub": "tester", "role": "admin", "name": "Test Admin"}


class _FakeSession:
    def __init__(self, values):
        self._values = iter(values)

    async def scalar(self, _query):
        return next(self._values)


def test_shadow_status_endpoint_reports_safe_mode(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "true")

    async def fake_get_db():
        yield _FakeSession([12, 5, 3])

    app = FastAPI()
    app.include_router(shadow_router)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _fake_admin_user

    with TestClient(app) as client:
        response = client.get("/shadow/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["shadow_mode"] is True
    assert payload["case_write_target"] == "shadow_cases"
    assert payload["enforcement_enabled"] is False
    assert payload["shadow_cases_total"] == 12
