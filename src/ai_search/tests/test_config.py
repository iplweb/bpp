"""Testy wykrywania stanu konfiguracji AI (``ai_search.config``)."""

import pytest

from ai_search import config


def test_disabled_is_not_configured(settings):
    settings.BPP_AI_SEARCH_ENABLED = False
    state = config.configuration_state()
    assert state.configured is False
    assert state.enabled is False
    assert "BPP_AI_SEARCH_ENABLED" in state.reason
    assert config.is_configured() is False


def test_anthropic_without_key_not_configured(settings, monkeypatch):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "anthropic"
    settings.BPP_AI_API_KEY = ""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    state = config.configuration_state()
    assert state.configured is False
    assert state.enabled is True
    assert "anthropic" in state.reason.lower()


def test_anthropic_with_settings_key_configured(settings, monkeypatch):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "anthropic"
    settings.BPP_AI_API_KEY = "sk-ant-test"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.is_configured() is True


def test_anthropic_with_env_key_configured(settings, monkeypatch):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "anthropic"
    settings.BPP_AI_API_KEY = ""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    assert config.is_configured() is True


def test_miscased_backend_treated_as_anthropic_needs_key(settings, monkeypatch):
    # 'Anthropic' (zła wielkość liter) -> traktowane jak anthropic -> wymaga
    # klucza (spójne z active_backend_name / get_backend).
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "Anthropic"
    settings.BPP_AI_API_KEY = ""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.is_configured() is False


def test_openai_without_base_url_not_configured(settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_BASE_URL = ""
    state = config.configuration_state()
    assert state.configured is False
    assert "BPP_AI_BASE_URL" in state.reason


def test_openai_with_base_url_configured(settings):
    settings.BPP_AI_SEARCH_ENABLED = True
    settings.BPP_AI_BACKEND = "openai"
    settings.BPP_AI_BASE_URL = "http://localhost:11434/v1"
    assert config.is_configured() is True


@pytest.mark.parametrize("enabled", [True, False])
def test_state_reports_active_backend(settings, enabled):
    settings.BPP_AI_SEARCH_ENABLED = enabled
    settings.BPP_AI_BACKEND = "openai"
    assert config.configuration_state().backend == "openai"
