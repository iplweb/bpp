"""URL pattern tests for pbn_wysylka_oswiadczen app."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_url_patterns():
    """Test URL patterns are correctly configured."""
    assert reverse("pbn_wysylka_oswiadczen:main") == "/pbn-wysylka-oswiadczen/"
    assert (
        reverse("pbn_wysylka_oswiadczen:publications")
        == "/pbn-wysylka-oswiadczen/publications/"
    )
    assert reverse("pbn_wysylka_oswiadczen:status") == "/pbn-wysylka-oswiadczen/status/"
    assert (
        reverse("pbn_wysylka_oswiadczen:status-partial")
        == "/pbn-wysylka-oswiadczen/status-partial/"
    )
    assert reverse("pbn_wysylka_oswiadczen:start") == "/pbn-wysylka-oswiadczen/start/"
    assert reverse("pbn_wysylka_oswiadczen:cancel") == "/pbn-wysylka-oswiadczen/cancel/"
    assert reverse("pbn_wysylka_oswiadczen:logs") == "/pbn-wysylka-oswiadczen/logs/"
    assert (
        reverse("pbn_wysylka_oswiadczen:log-detail", kwargs={"pk": 1})
        == "/pbn-wysylka-oswiadczen/logs/1/"
    )
