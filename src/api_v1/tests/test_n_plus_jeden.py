"""Regresja wydajnościowa publicznego API: brak N+1 i twardy cap paginacji.

Testy nie sprawdzają BEZWZGLĘDNEJ liczby zapytań (ta zmienia się przy każdej
refaktoryzacji i dawałaby fałszywe alarmy), tylko jej NIEZMIENNOŚĆ wobec
liczby wierszy na stronie. Endpoint listowy bez N+1 wykonuje tyle samo
zapytań dla 1 co dla 4 obiektów; endpoint z N+1 — o ``k * 3`` więcej.

Dlatego każdy obiekt dostaje WŁASNE (nie współdzielone) obiekty relacji —
przy współdzielonych Django trafiałby w cache instancji i N+1 by się ukrył.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from api_v1.pagination import BppLimitOffsetPagination
from bpp.models import (
    Autor,
    Autor_Jednostka,
    Patent,
    Patent_Autor,
    Praca_Doktorska,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.models.nagroda import Nagroda

#: Ile obiektów dokładamy po pomiarze bazowym (przy 1 obiekcie N+1 się nie
#: ujawnia — różnica musi być wielokrotnością liczby dołożonych wierszy).
DOKLADANE = 3


def _licz_zapytania(client, url):
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url)
    assert res.status_code == 200, res.content[:500]
    return len(ctx.captured_queries)


def _bez_n_plus_jeden(client, url, fabryka):
    """Zbuduj 1 + ``DOKLADANE`` obiektów i porównaj liczby zapytań.

    Pierwsze żądanie jest rozgrzewkowe (rozgrzewa cache ContentType, Site,
    Uczelnia), więc nie liczy się do pomiaru.
    """
    fabryka()
    _licz_zapytania(client, url)  # rozgrzewka
    bazowa = _licz_zapytania(client, url)

    for _ in range(DOKLADANE):
        fabryka()
    po_dolozeniu = _licz_zapytania(client, url)

    assert po_dolozeniu == bazowa, (
        f"N+1 na {url}: {bazowa} zapytań dla 1 obiektu, "
        f"{po_dolozeniu} dla {1 + DOKLADANE} "
        f"(+{po_dolozeniu - bazowa} na {DOKLADANE} dołożonych wierszy)"
    )


def _openaccess_ciagle():
    """Własne obiekty OpenAccess dla jednego wydawnictwa ciągłego."""
    return {
        "openaccess_tryb_dostepu": baker.make("bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle"),
        "openaccess_wersja_tekstu": baker.make("bpp.Wersja_Tekstu_OpenAccess"),
        "openaccess_licencja": baker.make("bpp.Licencja_OpenAccess"),
    }


def _openaccess_zwarte():
    return {
        "openaccess_tryb_dostepu": baker.make("bpp.Tryb_OpenAccess_Wydawnictwo_Zwarte"),
        "openaccess_wersja_tekstu": baker.make("bpp.Wersja_Tekstu_OpenAccess"),
        "openaccess_licencja": baker.make("bpp.Licencja_OpenAccess"),
    }


def _wydawnictwo_ciagle():
    return baker.make(Wydawnictwo_Ciagle, **_openaccess_ciagle())


@pytest.mark.django_db
def test_wydawnictwo_ciagle_lista_bez_n_plus_jeden(api_client):
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:wydawnictwo_ciagle-list"),
        _wydawnictwo_ciagle,
    )


@pytest.mark.django_db
def test_wydawnictwo_zwarte_lista_bez_n_plus_jeden(api_client):
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:wydawnictwo_zwarte-list"),
        lambda: baker.make(Wydawnictwo_Zwarte, **_openaccess_zwarte()),
    )


@pytest.mark.django_db
def test_praca_doktorska_lista_bez_n_plus_jeden(api_client, uczelnia, jednostka):
    # Praca_Doktorska nie dziedziczy pól openaccess_* (są tylko zadeklarowane
    # w serializerze) — jedyną relacją tekstową jest status_korekty.
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:praca_doktorska-list"),
        lambda: baker.make(Praca_Doktorska, jednostka=jednostka),
    )


@pytest.mark.django_db
def test_patent_lista_bez_n_plus_jeden(api_client):
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:patent-list"),
        lambda: baker.make(
            Patent, rodzaj_prawa=baker.make("bpp.Rodzaj_Prawa_Patentowego")
        ),
    )


@pytest.mark.django_db
def test_wydawnictwo_ciagle_autor_lista_bez_n_plus_jeden(
    api_client, uczelnia, jednostka
):
    # Jawna ``jednostka`` z fixture — inaczej baker tworzyłby przy każdym
    # wierszu NOWĄ Uczelnię, a ``Uczelnia.objects.get_for_request`` chodzi
    # wtedy inną ścieżką i zaszumia pomiar (liczba zapytań przestaje zależeć
    # wyłącznie od liczby wierszy).
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:wydawnictwo_ciagle_autor-list"),
        lambda: baker.make(Wydawnictwo_Ciagle_Autor, jednostka=jednostka),
    )


@pytest.mark.django_db
def test_patent_autor_lista_bez_n_plus_jeden(api_client, uczelnia, jednostka):
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:patent_autor-list"),
        lambda: baker.make(Patent_Autor, jednostka=jednostka),
    )


@pytest.mark.django_db
def test_autor_lista_bez_n_plus_jeden(api_client, uczelnia, jednostka):
    # /autor/ jest throttlowany (SearchAnonThrottle) — czyścimy licznik, żeby
    # kolejność testów w sesji nie wywołała 429 w środku pomiaru.
    cache.clear()

    def fabryka():
        autor = baker.make(Autor, pokazuj=True)
        baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
        return autor

    _bez_n_plus_jeden(api_client, reverse("api_v1:autor-list"), fabryka)


@pytest.mark.django_db
def test_nagroda_lista_bez_n_plus_jeden(api_client):
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    def fabryka():
        # Każda nagroda wskazuje na INNY rekord — GenericForeignKey bez
        # prefetcha oznacza wtedy jedno zapytanie na wiersz.
        return baker.make(Nagroda, content_type=ct, object_id=_wydawnictwo_ciagle().pk)

    _bez_n_plus_jeden(api_client, reverse("api_v1:nagroda-list"), fabryka)


@pytest.mark.django_db
def test_zrodlo_lista_bez_n_plus_jeden(api_client):
    _bez_n_plus_jeden(
        api_client,
        reverse("api_v1:zrodlo-list"),
        lambda: baker.make(
            Zrodlo,
            zasieg=baker.make("bpp.Zasieg_Zrodla"),
            openaccess_licencja=baker.make("bpp.Licencja_OpenAccess"),
        ),
    )


def test_globalna_paginacja_ma_max_limit():
    from rest_framework.settings import api_settings

    assert api_settings.DEFAULT_PAGINATION_CLASS is BppLimitOffsetPagination
    assert BppLimitOffsetPagination.max_limit == 500


@pytest.mark.django_db
def test_limit_jest_przycinany_do_max_limit(api_client, monkeypatch):
    """Żądanie ``?limit=999999`` dostaje co najwyżej ``max_limit`` wierszy.

    ``max_limit`` zaniżony do 2, żeby test nie musiał tworzyć 500 obiektów —
    sprawdzamy MECHANIZM (globalny paginator przycina), nie samą stałą; tę
    pilnuje ``test_globalna_paginacja_ma_max_limit``.
    """
    baker.make(Zrodlo, _quantity=3)
    monkeypatch.setattr(BppLimitOffsetPagination, "max_limit", 2)

    res = api_client.get(reverse("api_v1:zrodlo-list") + "?limit=999999")
    assert res.status_code == 200
    assert len(res.json()["results"]) == 2


@pytest.mark.django_db
def test_zapytanie_rekord_nie_ciagnie_search_index():
    """``/zapytanie/rekord/`` używa tego samego wąskiego ``only()`` co
    ``/szukaj/`` — tsvector ``search_index`` nie może trafiać do SELECT-a."""
    _wydawnictwo_ciagle()
    from bpp.models import Rekord

    Rekord.objects.full_refresh()

    user = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=user)

    with CaptureQueriesContext(connection) as ctx:
        res = client.get("/api/v1/zapytanie/rekord/", {"q": "rok >= 0"})
    assert res.status_code == 200

    winne = [q["sql"] for q in ctx.captured_queries if "search_index" in q["sql"]]
    assert not winne, f"search_index wyciągany do SELECT-a: {winne}"
