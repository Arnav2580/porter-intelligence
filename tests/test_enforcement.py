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
    from enforcement.dispatch import auto_enforce
    result = asyncio.run(
        auto_enforce(
            driver_id="D001",
            trip_id="T001",
            fraud_probability=0.90,
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

    # 0.999 → suspend
    r = asyncio.run(auto_enforce("D", "T", 0.999, "action", []))
    assert r["action"] == "suspend"

    # 0.95 → flag
    r = asyncio.run(auto_enforce("D", "T", 0.95, "action", []))
    assert r["action"] == "flag"
