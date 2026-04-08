"""Demo-control endpoint tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.demo import router as demo_router
from auth.dependencies import get_current_user
from database.connection import get_db


class _DeleteResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self, rowcounts=None):
        self.rowcounts = list(rowcounts or [])
        self.commits = 0

    async def execute(self, _query):
        if not self.rowcounts:
            raise AssertionError("Unexpected execute call")
        return _DeleteResult(self.rowcounts.pop(0))

    async def commit(self):
        self.commits += 1


def test_demo_scenarios_returns_presets():
    app = FastAPI()
    app.include_router(demo_router)

    with TestClient(app) as client:
        response = client.get("/demo/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_count"] == 3
    assert payload["recommended_order"][0] == "ring_walkthrough"


def test_demo_reset_clears_workspace_in_demo_mode(monkeypatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "demo")
    fake_session = _FakeSession(rowcounts=[8, 3, 5, 2, 1])

    app = FastAPI()
    app.include_router(demo_router)

    async def fake_get_db():
        yield fake_session

    async def fake_current_user():
        return {
            "sub": "ops_manager",
            "role": "ops_manager",
            "name": "Operations Manager",
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_current_user

    with TestClient(app) as client:
        response = client.post("/demo/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reset"] is True
    assert payload["deleted"]["fraud_cases"] == 5
    assert fake_session.commits == 1
