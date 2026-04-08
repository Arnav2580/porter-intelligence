"""Health contract tests."""

import asyncio

import api.main as main


class _FakeResult:
    async def execute(self, _query):
        return 1


class _FakeSessionManager:
    async def __aenter__(self):
        return _FakeResult()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_health_exposes_shadow_mode(monkeypatch):
    monkeypatch.setattr(main, "AsyncSessionLocal", _FakeSessionManager)

    async def fake_ping_redis():
        return True

    monkeypatch.setattr(main, "ping_redis", fake_ping_redis)
    main.app_state.clear()
    main.app_state.update(
        {
            "model": object(),
            "trips_df": [1, 2, 3],
            "runtime_mode": "prod",
            "synthetic_feed_enabled": False,
            "shadow_mode": True,
            "security_validation": {"ready": True, "warnings": []},
        }
    )

    payload = asyncio.run(main.health())

    assert payload["status"] == "ok"
    assert payload["shadow_mode"] is True
    assert "shadow-mode" in payload["data_provenance"].lower()
