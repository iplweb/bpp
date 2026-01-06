
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest


@pytest.mark.django_db
def test_multiseek_anonymous(client):
    """Test multiseek dla niezalogowanego użytkownika."""
    res = client.get(reverse("multiseek:index"))
    assert res.status_code == 200
    assert b"Adnotacje" not in res.content


@pytest.mark.django_db
def test_multiseek_logged_in(logged_in_client):
    """Test multiseek dla zalogowanego użytkownika."""
    res = logged_in_client.get(reverse("multiseek:index"))
    assert res.status_code == 200
    assert b"Adnotacje" in res.content
