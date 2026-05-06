import pytest

from app.main import _assert_no_github_models_in_production


def test_development_environment_allows_github_models(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEFAULT_MODEL", "github-dev")
    # Must not raise
    _assert_no_github_models_in_production()


def test_production_blocks_github_prefix(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEFAULT_MODEL", "github-dev")
    with pytest.raises(RuntimeError, match="GitHub Models must not serve production traffic"):
        _assert_no_github_models_in_production()


def test_production_blocks_github_slash_prefix(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEFAULT_MODEL", "github/gpt-4o-mini")
    with pytest.raises(RuntimeError, match="GitHub Models must not serve production traffic"):
        _assert_no_github_models_in_production()


def test_production_allows_openai_model(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Must not raise
    _assert_no_github_models_in_production()


def test_production_allows_anthropic_model(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-haiku")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    _assert_no_github_models_in_production()


def test_production_allows_local_model(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEFAULT_MODEL", "local")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    _assert_no_github_models_in_production()
