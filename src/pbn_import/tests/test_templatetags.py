"""Tests for PBN import template tags."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models import Uczelnia
from pbn_import.templatetags.pbn_import_tags import (
    bpp_admin_url,
    format_json,
    is_error_log,
    is_json,
    pbn_publication_url,
    truncate_message,
)


def test_pbn_publication_url_uses_public_pbn_root_without_request():
    url = pbn_publication_url({}, "pub-1")

    assert url == "https://pbn.nauka.gov.pl/core/#/publication/view/pub-1/current"


@pytest.mark.django_db
def test_pbn_publication_url_uses_request_uczelnia_root():
    request = object()
    uczelnia = Uczelnia(pbn_api_root="https://tenant.pbn.example/")

    with patch.object(Uczelnia.objects, "get_for_request", return_value=uczelnia):
        url = pbn_publication_url({"request": request}, "pub-1")

    assert url == "https://tenant.pbn.example/core/#/publication/view/pub-1/current"


def test_pbn_publication_url_returns_empty_for_missing_id():
    assert pbn_publication_url({}, "") == ""
    assert pbn_publication_url({}, None) == ""


@pytest.mark.django_db
def test_bpp_admin_url_builds_change_url(django_user_model):
    content_type = ContentType.objects.get_for_model(django_user_model)
    user = django_user_model.objects.create_user(username="admin-url-user")

    assert bpp_admin_url(content_type, user.pk) == f"/admin/bpp/bppuser/{user.pk}/change/"


def test_bpp_admin_url_returns_empty_for_missing_parts():
    assert bpp_admin_url(None, 1) == ""
    assert bpp_admin_url(SimpleNamespace(app_label="auth", model="user"), None) == ""


def test_format_json_pretty_prints_and_escapes_json_values():
    formatted = format_json({"key": "<script>"})

    assert '<pre class="json-display">' in formatted
    assert "&lt;script&gt;" in formatted
    assert "&quot;key&quot;:" in formatted


def test_format_json_parses_json_string_and_preserves_non_ascii():
    formatted = format_json('{"name": "Łódź"}')

    assert "Łódź" in formatted


def test_format_json_wraps_invalid_json_string():
    formatted = format_json("<not-json>")

    assert formatted == '<pre class="json-display">&lt;not-json&gt;</pre>'


def test_format_json_returns_empty_for_empty_value():
    assert format_json({}) == ""
    assert format_json("") == ""
    assert format_json(None) == ""


def test_is_json_accepts_only_valid_json_strings():
    assert is_json('{"ok": true}') is True
    assert is_json("[1, 2]") is True
    assert is_json("{broken") is False
    assert is_json({"ok": True}) is False
    assert is_json("") is False


@pytest.mark.parametrize("level", ["error", "critical", "warning"])
def test_is_error_log_accepts_error_like_levels(level):
    assert is_error_log(SimpleNamespace(level=level)) is True


@pytest.mark.parametrize("level", ["info", "success", "debug"])
def test_is_error_log_rejects_non_error_levels(level):
    assert is_error_log(SimpleNamespace(level=level)) is False


def test_truncate_message_handles_empty_short_and_long_values():
    assert truncate_message("") == ""
    assert truncate_message("short", length=10) == "short"
    assert truncate_message("abcdefghij", length=5) == "abcde..."
