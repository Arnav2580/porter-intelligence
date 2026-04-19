import asyncio
import os
import pytest


def test_auto_enforce_skips_watchlist():
    from enforcement.dispatch import auto_enforce
    result = asyncio.run(
        auto_enforce(
            driver_id="D001",
            trip_id="T001",
            fraud_probability=0.60,
            tier="watchlist",
            top_signals=["test"],
        )
    )
    assert result is None


def test_auto_enforce_skips_below_threshold():
    # Action threshold is read from model/weights/two_stage_config.json
    # (currently 0.80). Any probability below that must be skipped even
    # if the upstream tier label says "action".
    from enforcement.dispatch import auto_enforce
    result = asyncio.run(
        auto_enforce(
            driver_id="D001",
            trip_id="T001",
            fraud_probability=0.70,
            tier="action",
            top_signals=["test"],
        )
    )
    assert result is None


def test_auto_enforce_log_only_mode():
    os.environ.pop("PORTER_DISPATCH_URL", None)
    # Force reload so the module picks up the unset env var
    import importlib
    import enforcement.dispatch as ed
    ed.PORTER_DISPATCH_URL = ""

    from enforcement.dispatch import auto_enforce
    result = asyncio.run(
        auto_enforce(
            driver_id="D001",
            trip_id="T001",
            fraud_probability=0.999,
            tier="action",
            top_signals=["Cash payment", "Night trip"],
        )
    )
    assert result is not None
    assert result["sent"] is False
    assert result["mode"] == "log_only"
    assert result["action"] == "suspend"


def test_action_severity_levels():
    os.environ.pop("PORTER_DISPATCH_URL", None)
    import enforcement.dispatch as ed
    ed.PORTER_DISPATCH_URL = ""

    from enforcement.dispatch import auto_enforce

    # 0.999 → suspend (>= 0.95)
    r = asyncio.run(auto_enforce("D", "T", 0.999, "action", []))
    assert r["action"] == "suspend"

    # 0.90 → flag (>= 0.85, < 0.95)
    r = asyncio.run(auto_enforce("D", "T", 0.90, "action", []))
    assert r["action"] == "flag"

    # 0.82 → alert (>= 0.80 action threshold, < 0.85)
    r = asyncio.run(auto_enforce("D", "T", 0.82, "action", []))
    assert r["action"] == "alert"


def test_auto_enforce_skips_when_shadow_mode_enabled(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "true")
    from enforcement.dispatch import auto_enforce

    result = asyncio.run(
        auto_enforce(
            driver_id="D001",
            trip_id="T001",
            fraud_probability=0.999,
            tier="action",
            top_signals=["test"],
        )
    )
    assert result is None
