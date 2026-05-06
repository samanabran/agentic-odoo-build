import pytest

from app.main import get_active_model


def test_private_mode_overrides_production(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert get_active_model() == "prod-local"


def test_private_mode_overrides_development(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert get_active_model() == "prod-local"


def test_production_routes_to_prod_default(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "false")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert get_active_model() == "prod-default"


def test_development_routes_to_github_dev(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert get_active_model() == "github-dev"


def test_staging_environment_raises(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "false")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(RuntimeError, match="not a recognised value"):
        get_active_model()


def test_unset_environment_raises(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "false")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(RuntimeError, match="not a recognised value"):
        get_active_model()


def test_private_mode_case_insensitive(monkeypatch):
    monkeypatch.setenv("PRIVATE_MODE", "TRUE")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert get_active_model() == "prod-local"
