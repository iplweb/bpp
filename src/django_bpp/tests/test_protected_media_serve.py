"""Testy guardu ``protected_media_serve`` — ochrona przed path-traversal.

Widok testujemy BEZPOŚREDNIO (nie przez test client), bo klient normalizuje
URL zanim trafi do widoku i zamaskowałby lukę. ``static_serve`` jest mockowany,
żeby test nie zależał od plików na dysku i żeby dało się odróżnić *dlaczego*
podniesiono Http404 (guard vs. brak pliku).
"""

from unittest import mock

import pytest
from django.http import Http404
from django.test import RequestFactory

from django_bpp.urls import protected_media_serve


@pytest.fixture
def request_get():
    return RequestFactory().get("/media/whatever")


def test_traversal_do_protected_jest_blokowany(request_get):
    """public/../protected/... zwija się do protected/ — musi być blokowany."""
    with mock.patch("django_bpp.urls.static_serve") as m:
        with pytest.raises(Http404, match="Use the download endpoint"):
            protected_media_serve(request_get, path="public/../protected/secret.pdf")
        m.assert_not_called()


def test_traversal_wielosegmentowy_jest_blokowany(request_get):
    """Wiele ../ też musi zostać znormalizowane przed sprawdzeniem guardu."""
    with mock.patch("django_bpp.urls.static_serve") as m:
        with pytest.raises(Http404, match="Use the download endpoint"):
            protected_media_serve(request_get, path="a/b/../../protected/x.pdf")
        m.assert_not_called()


def test_bezposredni_protected_dalej_blokowany(request_get):
    """Regresja: bezpośrednie protected/... ma dalej być blokowane."""
    with mock.patch("django_bpp.urls.static_serve") as m:
        with pytest.raises(Http404, match="Use the download endpoint"):
            protected_media_serve(request_get, path="protected/secret.pdf")
        m.assert_not_called()


def test_legalny_public_jest_serwowany(request_get):
    """Legalna ścieżka public/ nie może być blokowana przez guard."""
    sentinel = object()
    with mock.patch("django_bpp.urls.static_serve", return_value=sentinel) as m:
        result = protected_media_serve(
            request_get, path="public/plik.pdf", document_root="/media"
        )
    assert result is sentinel
    m.assert_called_once()
