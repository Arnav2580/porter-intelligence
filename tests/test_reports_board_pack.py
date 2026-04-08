"""Board-pack PDF endpoint tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.reports import router as reports_router
from api.state import app_state
from auth.dependencies import get_current_user
from database.connection import get_db


class _FakeSession:
    def __init__(self, scalar_results=None):
        self.scalar_results = list(scalar_results or [])

    async def scalar(self, _query):
        if not self.scalar_results:
            raise AssertionError("Unexpected scalar call")
        return self.scalar_results.pop(0)


def test_board_pack_returns_pdf(monkeypatch):
    monkeypatch.setitem(
        app_state,
        "report",
        {
            "xgboost": {
                "total_trips": 100000,
                "total_fraud": 5895,
                "net_recoverable_per_trip": 6.7959,
            },
            "two_stage": {
                "action_precision": 0.883,
                "action_fpr": 0.0053,
                "net_recoverable_per_trip": 6.7959,
                "total_fraud_caught_pct": 81.5,
            },
        },
    )
    fake_session = _FakeSession(
        scalar_results=[120, 34, 6, 182500.0]
    )

    app = FastAPI()
    app.include_router(reports_router)

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
        response = client.get("/reports/board-pack")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
