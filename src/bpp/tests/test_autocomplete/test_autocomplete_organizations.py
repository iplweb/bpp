"""
Organization and unit-related autocomplete tests.

This module contains tests for:
- Jednostka (unit) autocomplete functionality
- Wydawca (publisher) autocomplete
- Wydawnictwo nadrzedne (parent publication) autocomplete
"""

import json

from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte
from bpp.views.autocomplete import JednostkaMixin


def test_JednostkaMixin_get_result_label(jednostka):
    """Test that JednostkaMixin returns a label even without wydzial."""
    jednostka.wydzial = None
    assert JednostkaMixin().get_result_label(jednostka)


def test_wydawca_autocomplete(admin_client):
    """Test wydawca (publisher) autocomplete endpoint."""
    from django.urls import reverse

    res = admin_client.get(reverse("bpp:wydawca-autocomplete"))
    assert res.status_code == 200


def test_wydawnictwo_nadrzedne_autocomplete(admin_client):
    """Test wydawnictwo nadrzedne autocomplete endpoint."""
    from django.urls import reverse

    admin_client.get(reverse("bpp:wydawnictwo-nadrzedne-autocomplete") + "?q=test")


def test_publicwydawnictwo_nadrzedne_autocomplete(admin_client, ksiazka):
    """Test public wydawnictwo nadrzedne autocomplete with parent publications."""
    from django.urls import reverse

    ksiazka.tytul_oryginalny = "test 123"
    ksiazka.save()

    res = admin_client.get(
        reverse("bpp:public-wydawnictwo-nadrzedne-autocomplete") + "?q=test"
    )
    assert not json.loads(res.content)["results"]

    baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=ksiazka)
    res = admin_client.get(
        reverse("bpp:public-wydawnictwo-nadrzedne-autocomplete") + "?q=test"
    )
    assert len(json.loads(res.content)["results"]) == 1
