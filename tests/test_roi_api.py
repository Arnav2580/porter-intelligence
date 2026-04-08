"""ROI calculator API tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.roi import router as roi_router
from api.state import app_state


def test_roi_calculator_returns_scenarios(monkeypatch):
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
                "total_trips": 100000,
                "net_recoverable_per_trip": 6.7959,
                "action_precision": 0.883,
            },
        },
    )

    app = FastAPI()
    app.include_router(roi_router)

    with TestClient(app) as client:
        response = client.post(
            "/roi/calculate",
            json={
                "gmv_crore": 2500,
                "trips_per_day": 43200,
                "fraud_rate_pct": 5.895,
                "platform_price_crore": 3.25,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["annual_savings_crore"] > 0
    assert payload["payback_months"] > 0
    assert payload["roi_pct"] > 0
    assert payload["benchmark_net_recoverable_per_trip"] == 6.7959
    assert len(payload["scenarios"]) == 3
    assert payload["scenarios"][1]["scenario"] == "realistic"
    assert (
        payload["scenarios"][1]["annual_savings_crore"]
        == payload["annual_savings_crore"]
    )


def test_roi_calculator_falls_back_to_saved_benchmark(monkeypatch):
    monkeypatch.setitem(app_state, "report", {})

    app = FastAPI()
    app.include_router(roi_router)

    with TestClient(app) as client:
        response = client.post(
            "/roi/calculate",
            json={
                "gmv_crore": 2500,
                "trips_per_day": 43200,
                "fraud_rate_pct": 5.895,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmark_net_recoverable_per_trip"] > 0
