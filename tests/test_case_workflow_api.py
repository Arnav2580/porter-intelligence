"""Analyst workflow API and helper tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.cases import (
    _build_case_history,
    router as cases_router,
)
from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import (
    AuditLog,
    DriverAction,
    DriverActionType,
    FraudCase,
    FraudCaseStatus,
)


class _FakeResult:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = scalars or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars


class _FakeSession:
    def __init__(self, execute_results=None, scalar_results=None):
        self.execute_results = list(execute_results or [])
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.commits = 0

    async def execute(self, _query):
        if not self.execute_results:
            raise AssertionError("Unexpected execute call")
        return self.execute_results.pop(0)

    async def scalar(self, _query):
        if not self.scalar_results:
            raise AssertionError("Unexpected scalar call")
        return self.scalar_results.pop(0)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


def _make_case(
    *,
    tier: str = "action",
    status: FraudCaseStatus = FraudCaseStatus.OPEN,
    assigned_to: str | None = None,
) -> FraudCase:
    created_at = datetime.now(timezone.utc) - timedelta(hours=3)
    return FraudCase(
        id=uuid.uuid4(),
        trip_id="TRIP-001",
        driver_id="DRV-001",
        zone_id="blr_koramangala",
        tier=tier,
        fraud_probability=0.97,
        top_signals=["Cash payment detected", "Fare inflated 4.2x"],
        fare_inr=860.0,
        recoverable_inr=129.0,
        status=status,
        assigned_to=assigned_to,
        created_at=created_at,
    )


def _make_app(fake_session: _FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(cases_router)

    async def fake_get_db():
        yield fake_session

    async def fake_current_user():
        return {
            "sub": "analyst_1",
            "role": "ops_analyst",
            "name": "Fraud Analyst",
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_current_user
    return TestClient(app)


def test_action_false_alarm_requires_override_reason():
    case = _make_case(tier="action")
    fake_session = _FakeSession(
        execute_results=[_FakeResult(scalar=case)]
    )

    with _make_app(fake_session) as client:
        response = client.patch(
            f"/cases/{case.id}",
            json={
                "status": "false_alarm",
                "analyst_notes": "No clear fraud pattern found.",
            },
        )

    assert response.status_code == 400
    assert "override_reason" in response.json()["detail"]
    assert fake_session.commits == 0


def test_batch_review_updates_multiple_cases_and_claims_them():
    case_one = _make_case(tier="watchlist")
    case_two = _make_case(tier="watchlist")
    fake_session = _FakeSession(
        execute_results=[
            _FakeResult(
                scalars=[case_one, case_two],
            )
        ]
    )

    with _make_app(fake_session) as client:
        response = client.post(
            "/cases/batch-review",
            json={
                "case_ids": [str(case_one.id), str(case_two.id)],
                "status": "under_review",
                "analyst_notes": "Bulk triage started.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_count"] == 2
    assert payload["status"] == "under_review"
    assert case_one.status == FraudCaseStatus.UNDER_REVIEW
    assert case_two.status == FraudCaseStatus.UNDER_REVIEW
    assert case_one.assigned_to == "analyst_1"
    assert case_two.assigned_to == "analyst_1"
    assert fake_session.commits == 1
    assert len(fake_session.added) == 2


def test_case_history_includes_creation_status_and_driver_action():
    case = _make_case(status=FraudCaseStatus.ESCALATED)
    audit = AuditLog(
        action="case_status_change",
        resource="fraud_case",
        resource_id=str(case.id),
        user_id="analyst_1",
        details={
            "old_status": "open",
            "new_status": "escalated",
            "notes": "Escalated due to ring overlap.",
        },
        created_at=case.created_at + timedelta(minutes=15),
    )
    driver_action = DriverAction(
        driver_id=case.driver_id,
        action_type=DriverActionType.SUSPEND,
        reason="Temporary suspension pending review.",
        performed_by="ops_manager",
        case_id=str(case.id),
        created_at=case.created_at + timedelta(minutes=30),
    )

    history = _build_case_history(case, [audit], [driver_action])

    assert len(history) == 3
    assert history[0]["category"] == "driver_action"
    assert history[1]["category"] == "status_change"
    assert history[-1]["category"] == "case_created"
    assert "Escalated" in history[1]["description"]
