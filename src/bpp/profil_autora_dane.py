"""Budowanie danych poszczególnych sekcji profilu autora.

Każdy builder dostaje (autor, limit, request) i zwraca słownik z danymi dla
szablonu albo ``None``, gdy sekcja jest pusta (wtedy zostaje automatycznie
ukryta, nawet jeśli włączona w konfiguracji). Modele importujemy leniwie, żeby
ten moduł dało się zaimportować wcześnie (np. w widoku).

Uwaga dot. ``Rekord.objects.prace_autora`` — queryset robi
``filter(autorzy__autor=...).distinct()``. Dla list (order_by + slice) join na
``autorzy`` zwija się przez DISTINCT (wszystkie kolumny pochodzą z rekordu).
Dla histogramów pobieramy pary ``(id, X)`` — włączenie unikalnego ``id`` do
DISTINCT neutralizuje duplikaty z joinu, a właściwy rozkład liczymy w Pythonie
(zbiór prac jednego autora jest ograniczony).
"""

from collections import Counter

from django.db.models import Q, Sum

from bpp import const
from bpp.profil_autora import (
    KLUCZ_DYSCYPLINY,
    KLUCZ_NAJLEPSZE_IF,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_NAJNOWSZE_ARTYKULY,
    KLUCZ_NAJNOWSZE_ZWARTE,
    KLUCZ_OSTATNIO_EDYTOWANE,
    KLUCZ_PUNKTY_LATA,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WSPOLAUTORZY,
    KLUCZ_WYBRANE_PUBLIKACJE,
    KLUCZ_WYKRES_LATA,
    KLUCZ_ZRODLA,
)

_SELECT_RELATED = ("charakter_formalny", "zrodlo", "wydawca")


def _lista(qs, limit):
    prace = list(qs.select_related(*_SELECT_RELATED)[:limit])
    return {"prace": prace} if prace else None


def _prace(autor):
    from bpp.models import Rekord

    return Rekord.objects.prace_autora(autor)


# --- buildery sekcji -------------------------------------------------------


def _najlepsze_pk(autor, limit, request):
    return _lista(
        _prace(autor).filter(punkty_kbn__gt=0).order_by("-punkty_kbn", "-rok"), limit
    )


def _najlepsze_if(autor, limit, request):
    return _lista(
        _prace(autor).filter(impact_factor__gt=0).order_by("-impact_factor", "-rok"),
        limit,
    )


def _najnowsze_artykuly(autor, limit, request):
    return _lista(
        _prace(autor)
        .filter(charakter_formalny__charakter_ogolny=const.CHARAKTER_OGOLNY_ARTYKUL)
        .order_by("-rok"),
        limit,
    )


def _najnowsze_zwarte(autor, limit, request):
    return _lista(
        _prace(autor)
        .filter(
            charakter_formalny__charakter_ogolny__in=[
                const.CHARAKTER_OGOLNY_KSIAZKA,
                const.CHARAKTER_OGOLNY_ROZDZIAL,
            ]
        )
        .order_by("-rok"),
        limit,
    )


def _ostatnio_edytowane(autor, limit, request):
    return _lista(_prace(autor).order_by("-ostatnio_zmieniony"), limit)


def _wybrane_publikacje(autor, limit, request):
    wybrane = list(
        autor.wybrane_publikacje.select_related("content_type").order_by("kolejnosc")
    )
    prace = [w.publikacja for w in wybrane if w.publikacja is not None]
    return {"prace": prace} if prace else None


def _statystyki_charakter(autor, limit, request):
    pary = _prace(autor).values_list("id", "charakter_formalny__nazwa")
    licznik = Counter(nazwa for _id, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))
    return {"wiersze": wiersze, "suma": sum(licznik.values())}


def _wykres_lata(autor, limit, request):
    pary = _prace(autor).values_list("id", "rok")
    licznik = Counter(rok for _id, rok in pary if rok is not None)
    if not licznik:
        return None
    dane = sorted(licznik.items())
    maks = max(licznik.values())
    return {"dane": dane, "maks": maks}


def _punkty_lata(autor, limit, request):
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Query

    wiersze = list(
        Cache_Punktacja_Autora_Query.objects.filter(autor=autor)
        .values("rekord__rok")
        .annotate(pkd=Sum("pkdaut"), sloty=Sum("slot"))
        .order_by("rekord__rok")
    )
    return {"wiersze": wiersze} if wiersze else None


def _dyscypliny(autor, limit, request):
    from bpp.models import Autorzy

    pary = (
        Autorzy.objects.filter(autor=autor)
        .exclude(dyscyplina_naukowa=None)
        .values_list("rekord_id", "dyscyplina_naukowa__nazwa")
        .distinct()
    )
    licznik = Counter(nazwa for _r, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))
    return {"wiersze": wiersze, "suma": sum(licznik.values())}


def _zrodla(autor, limit, request):
    pary = _prace(autor).exclude(zrodlo=None).values_list("id", "zrodlo__nazwa")
    licznik = Counter(nazwa for _id, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return {"wiersze": wiersze}


def _wspolautorzy(autor, limit, request):
    from powiazania_autorow.models import AuthorConnection

    polaczenia = (
        AuthorConnection.objects.filter(
            Q(primary_author=autor) | Q(secondary_author=autor)
        )
        .select_related("primary_author", "secondary_author")
        .order_by("-shared_publications_count")[:limit]
    )
    wspolautorzy = []
    for p in polaczenia:
        inny = (
            p.secondary_author if p.primary_author_id == autor.pk else p.primary_author
        )
        wspolautorzy.append({"autor": inny, "liczba": p.shared_publications_count})
    return {"wspolautorzy": wspolautorzy} if wspolautorzy else None


_BUILDERY = {
    KLUCZ_NAJLEPSZE_PK: _najlepsze_pk,
    KLUCZ_NAJLEPSZE_IF: _najlepsze_if,
    KLUCZ_NAJNOWSZE_ARTYKULY: _najnowsze_artykuly,
    KLUCZ_NAJNOWSZE_ZWARTE: _najnowsze_zwarte,
    KLUCZ_OSTATNIO_EDYTOWANE: _ostatnio_edytowane,
    KLUCZ_WYBRANE_PUBLIKACJE: _wybrane_publikacje,
    KLUCZ_STATYSTYKI_CHARAKTER: _statystyki_charakter,
    KLUCZ_WYKRES_LATA: _wykres_lata,
    KLUCZ_PUNKTY_LATA: _punkty_lata,
    KLUCZ_DYSCYPLINY: _dyscypliny,
    KLUCZ_ZRODLA: _zrodla,
    KLUCZ_WSPOLAUTORZY: _wspolautorzy,
}


def przygotuj_sekcje(autor, uczelnia=None, request=None):
    """Zwróć listę sekcji prawej kolumny do wyrenderowania (z danymi).

    Układ pobierany jest globalnie z ``uczelnia`` (``rozwiaz_uklad``), dane —
    z ``autor``. Każdy element: ``{"klucz", "nazwa", "template", "dane"}``.
    ``dane`` to słownik zwrócony przez builder. Sekcje, których builder zwrócił
    ``None`` (lub które nie mają jeszcze buildera), są pomijane.
    """
    from bpp.profil_autora import rozwiaz_uklad

    sekcje = []
    for s in rozwiaz_uklad(uczelnia):
        builder = _BUILDERY.get(s["klucz"])
        if builder is None:
            continue
        dane = builder(autor, s["limit"], request)
        if dane is None:
            continue
        sekcje.append(
            {
                "klucz": s["klucz"],
                "nazwa": s["nazwa"],
                "template": s["template"],
                "dane": dane,
            }
        )
    return sekcje
