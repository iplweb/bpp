"""Brak stałego wpisu słownika nie może wywalać list w API (patrz slowniki_stale).

``Patent``/``Praca_Doktorska``/``Praca_Habilitacyjna`` biorą
``charakter_formalny`` (``Patent`` także ``jezyk``) zapytaniem do słownika.
Dawniej brak wiersza (np. po TRUNCATE w testach albo usunięty/przemianowany
skrót na produkcji) dawał ``DoesNotExist`` -> 500 na całej liście API.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Charakter_Formalny, Jezyk, Patent, Praca_Doktorska
from bpp.models.patent import _Patent_PropertyCache
from bpp.models.praca_doktorska import _Praca_Doktorska_PropertyCache
from bpp.models.praca_habilitacyjna import (
    Praca_Habilitacyjna,
    _Praca_Habilitacyjna_PropertyCache,
)
from bpp.models.slowniki_stale import cached_if_found

_CACHE_MODULOW = (
    (_Patent_PropertyCache, ("charakter_formalny", "jezyk")),
    (
        _Praca_Doktorska_PropertyCache,
        ("charakter_formalny", "typ_odpowiedzialnosci_autor"),
    ),
    (_Praca_Habilitacyjna_PropertyCache, ("charakter_formalny",)),
)


@pytest.fixture
def czysty_cache_slownikow():
    def wyczysc():
        for cache_modulu, nazwy in _CACHE_MODULOW:
            for nazwa in nazwy:
                cache_modulu.__dict__.pop(nazwa, None)

    wyczysc()
    yield
    wyczysc()


def test_cached_if_found_nie_zapamietuje_none():
    wyniki = iter([None, "wpis", "inny"])

    class Cache:
        @cached_if_found
        def wartosc(self):
            return next(wyniki)

    obj = Cache()
    assert obj.wartosc is None  # brak -> None, NIE do cache
    assert obj.wartosc == "wpis"  # kolejne odwołanie pyta ponownie
    assert obj.wartosc == "wpis"  # znaleziony -> zapamiętany
    obj.__dict__.pop("wartosc")  # czyszczenie jak w fixtures testów
    assert obj.wartosc == "inny"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "model", "skrot"),
    [
        ("api_v1:patent-list", Patent, "PAT"),
        ("api_v1:praca_doktorska-list", Praca_Doktorska, "D"),
        ("api_v1:praca_habilitacyjna-list", Praca_Habilitacyjna, "H"),
    ],
)
def test_lista_api_bez_wpisu_slownika(
    api_client, czysty_cache_slownikow, url_name, model, skrot
):
    Charakter_Formalny.objects.filter(skrot=skrot).delete()
    Jezyk.objects.filter(nazwa__icontains="polski").delete()
    baker.make(model)

    res = api_client.get(reverse(url_name))

    assert res.status_code == 200, res.content[:500]
    (wiersz,) = res.json()["results"]
    assert wiersz["charakter_formalny"] is None
    if model is Patent:
        assert wiersz["jezyk"] is None


@pytest.mark.django_db
def test_wpis_slownika_pojawia_sie_bez_restartu(czysty_cache_slownikow):
    Charakter_Formalny.objects.filter(skrot="PAT").delete()
    assert _Patent_PropertyCache.charakter_formalny is None

    nowy = baker.make(Charakter_Formalny, skrot="PAT", nazwa="Patent")

    assert _Patent_PropertyCache.charakter_formalny == nowy
