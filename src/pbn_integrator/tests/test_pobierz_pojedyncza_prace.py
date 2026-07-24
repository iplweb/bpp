"""Kontrakt ``_pobierz_pojedyncza_prace`` wobec „praca nie istnieje w PBN”.

Po P3 rozpoznanie 422 „was not exists!” robi **RAZ** endpoint paczki
(``pbn_client``'owy ``get_publication_by_id`` rzuca ``PublicationNotFound``).
BPP nie duplikuje już tej detekcji — tylko **propaguje** wyjątek do handlerów.
``BrakIDPracyPoStroniePBN`` jest aliasem ``PublicationNotFound`` (ta sama klasa),
więc istniejące ``except BrakIDPracyPoStroniePBN`` łapią wyjątek z paczki.

Decyzja 404: zwykły 404 NIE jest mapowany na „brak pracy” (bywa przejściowy) —
leci dalej jako zwykły ``HttpException`` i nie kasuje lokalnego cache'u.
"""

from unittest.mock import MagicMock

import pytest


def _client_raising(exc):
    client = MagicMock()
    client.get_publication_by_id.side_effect = exc
    return client


def test_brak_id_to_alias_publication_not_found():
    """Inwariant P3: to DOKŁADNIE ta sama klasa (``is``), nie podklasa."""
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, PublicationNotFound

    assert BrakIDPracyPoStroniePBN is PublicationNotFound


def test_publication_not_found_z_paczki_propaguje_jako_brak_id():
    """Paczka rzuca ``PublicationNotFound`` → BPP propaguje (== BrakID),

    z zachowaniem pól HTTP (status/url/content).
    """
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, PublicationNotFound
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    content = f"Publication with ID {pub_id} was not exists!"
    exc = PublicationNotFound(422, "https://pbn/x", content)
    with pytest.raises(BrakIDPracyPoStroniePBN) as ei:
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)
    assert ei.value.status_code == 422
    assert ei.value.url == "https://pbn/x"
    assert ei.value.content == content


def test_zwykly_404_nie_jest_brak_id():
    """Decyzja P3: 404 (przejściowy) NIE jest „brak pracy” — leci jako

    zwykły ``HttpException`` i nie triggeruje kasowania cache'u.
    """
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    exc = HttpException(404, "https://pbn/x", "Not Found")
    with pytest.raises(HttpException) as ei:
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)
    assert not isinstance(ei.value, BrakIDPracyPoStroniePBN)


def test_goly_422_nie_jest_juz_re_detektowany_przez_bpp():
    """Regresja P3: BPP NIE re-detektuje już markera w treści. Gdyby paczka

    (wbrew kontraktowi) rzuciła goły ``HttpException`` z 422 zamiast
    ``PublicationNotFound``, BPP propaguje go bez zmiany typu — rozpoznanie
    jest odpowiedzialnością endpointu paczki, nie call-site'u BPP.
    """
    from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    exc = HttpException(
        422, "https://pbn/x", f"Publication with ID {pub_id} was not exists!"
    )
    with pytest.raises(HttpException) as ei:
        publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)
    assert not isinstance(ei.value, BrakIDPracyPoStroniePBN)


def test_500_internal_server_error_zwraca_none():
    """500 „Internal server error” to nie „brak pracy” — logujemy i zwracamy

    ``None`` (praca do pominięcia, bez wysadzania batcha).
    """
    from pbn_api.exceptions import HttpException
    from pbn_integrator.utils import publications

    pub_id = "60a1f2c3d4e5f60718293a4b"
    exc = HttpException(500, "https://pbn/x", "Internal server error")
    result = publications._pobierz_pojedyncza_prace(_client_raising(exc), pub_id)
    assert result is None
