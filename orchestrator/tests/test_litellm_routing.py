"""
Tests: LiteLLM routing — verifies get_active_model() and provider endpoint config (M2).
"""
import pytest


def test_dev_routing_uses_github_dev(monkeypatch):
    """In development mode, active model must be github-dev."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("PRIVATE_MODE", raising=False)
    from app.main import get_active_model

    assert get_active_model() == "github-dev"


def test_production_routing_uses_prod_default(monkeypatch):
    """In production mode, active model must be prod-default."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("PRIVATE_MODE", raising=False)
    from app.main import get_active_model

    assert get_active_model() == "prod-default"


def test_private_mode_overrides_environment(monkeypatch):
    """PRIVATE_MODE=true forces prod-local regardless of ENVIRONMENT."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("PRIVATE_MODE", "true")
    from app.main import get_active_model

    assert get_active_model() == "prod-local"


def test_private_mode_in_dev_overrides_to_local(monkeypatch):
    """PRIVATE_MODE=true in development also resolves to prod-local."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("PRIVATE_MODE", "true")
    from app.main import get_active_model

    assert get_active_model() == "prod-local"


def test_unknown_environment_raises(monkeypatch):
    """Any unrecognised ENVIRONMENT value must raise RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("PRIVATE_MODE", raising=False)
    from app.main import get_active_model

    with pytest.raises(RuntimeError, match="staging"):
        get_active_model()
