"""Przełącznik widoczności eksportu CERIF z obiektu ``Uczelnia``.

``Uczelnia.eksport_cerif_wlaczony`` jest domyślnie WŁĄCZONY — istniejące
wdrożenia nie zmieniają zachowania.

Wyłączony przełącznik daje **404**, nie 403/401 — endpoint ma wyglądać na
nieistniejący, a nie na „istnieje, ale nie dla ciebie".

Przełączniki ``/api/v1/`` mieszkają we własnej aplikacji:
``src/api_v1/tests/test_przelaczniki.py``.
"""

import pytest
from django.urls import NoReverseMatch, reverse


def _url_cerif():
    """URL endpointu OAI-PMH albo ``None``, gdy jeszcze nie istnieje.

    ``cerif_export/urls.py`` powstaje w Fazie 2 — do tego czasu testy
    przełącznika CERIF są pomijane (patrz ``skipif`` niżej).
    """
    try:
        return reverse("cerif_export:oai")
    except NoReverseMatch:
        return None


URL_CERIF = _url_cerif()

bez_endpointu_cerif = pytest.mark.skipif(
    URL_CERIF is None,
    reason="cerif_export:oai nie istnieje — endpoint powstaje w Fazie 2",
)


#
# CERIF — Uczelnia.eksport_cerif_wlaczony (odblokowuje się w Fazie 2)
#


def test_eksport_cerif_wlaczony_domyslnie(uczelnia):
    """Default=True — CERIF startuje aktywny."""
    assert uczelnia.eksport_cerif_wlaczony is True


@bez_endpointu_cerif
def test_cerif_domyslnie_odpowiada(client, uczelnia):
    res = client.get(URL_CERIF, {"verb": "Identify"})
    assert res.status_code == 200


@bez_endpointu_cerif
def test_cerif_wylaczony_daje_404(client, uczelnia):
    """Analogicznie do ``/api/v1/``: wyłączony eksport = endpoint nie
    istnieje (404), a nie „istnieje, ale odmawia" (403)."""
    uczelnia.eksport_cerif_wlaczony = False
    uczelnia.save()

    res = client.get(URL_CERIF, {"verb": "Identify"})
    assert res.status_code == 404


@pytest.mark.django_db
def test_endpoint_cerif_przyjmuje_post(uczelnia, settings):
    """OAI-PMH 2.0 wymaga POST — harvester nie ma tokenu CSRF.

    Regresja: bez ``csrf_exempt`` na widoku POST kończył się odpowiedzią
    403. Domyślny klient testowy Django nie wychwyciłby tego, bo omija
    sprawdzanie CSRF — stąd jawne ``enforce_csrf_checks``.
    """
    from django.test import Client

    settings.ALLOWED_HOSTS = ["*"]
    klient = Client(enforce_csrf_checks=True)

    odpowiedz = klient.post(
        reverse("cerif_export:oai"),
        {"verb": "Identify"},
        HTTP_HOST=uczelnia.site.domain,
    )

    assert odpowiedz.status_code == 200
    assert b"<Identify" in odpowiedz.content
