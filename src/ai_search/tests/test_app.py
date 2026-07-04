from django.apps import apps
from django.conf import settings


def test_app_registered():
    assert apps.is_installed("ai_search")


def test_ai_settings_present():
    assert hasattr(settings, "BPP_AI_MODEL")
    assert settings.BPP_AI_MODEL
    assert "claude-sonnet-5" in settings.BPP_AI_PRICING
