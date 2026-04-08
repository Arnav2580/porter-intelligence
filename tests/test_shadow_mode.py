"""Shadow-mode runtime and persistence tests."""

from runtime_config import get_runtime_settings


def test_runtime_settings_reads_shadow_mode(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "true")
    settings = get_runtime_settings()
    assert settings.shadow_mode is True


def test_case_storage_target_switches_to_shadow(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "true")
    from database.case_store import get_case_storage_target

    target = get_case_storage_target()
    assert target.storage_mode == "shadow"
    assert target.table_name == "shadow_cases"


def test_case_storage_target_defaults_live(monkeypatch):
    monkeypatch.setenv("SHADOW_MODE", "false")
    from database.case_store import get_case_storage_target

    target = get_case_storage_target()
    assert target.storage_mode == "live"
    assert target.table_name == "fraud_cases"
