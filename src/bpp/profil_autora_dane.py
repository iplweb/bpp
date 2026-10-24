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
from decimal import Decimal

from django.db.models import Q, Sum

from bpp import const
from bpp.profil_autora import (
    KLUCZ_DYSCYPLINY,
    KLUCZ_NAJLEPSZE_IF,
    KLUCZ_NAJLEPSZE_PK,
    KLUCZ_NAJNOWSZE_ARTYKULY,
    KLUCZ_NAJNOWSZE_ZWARTE,
    KLUCZ_OSTATNIO_EDYTOWANE,
    KLUCZ_PODSUMOWANIE,
    KLUCZ_PUNKTY_LATA,
    KLUCZ_STATYSTYKI_CHARAKTER,
    KLUCZ_WSPOLAUTORZY,
    KLUCZ_WYBRANE_PUBLIKACJE,
    KLUCZ_WYKRESY,
    KLUCZ_ZRODLA,
)

_SELECT_RELATED = ("charakter_formalny", "zrodlo", "wydawca")


def _lista(qs, limit):
    prace = list(qs.select_related(*_SELECT_RELATED)[:limit])
    return {"prace": prace} if prace else None


def _uczelnia(request):
    from bpp.models import Uczelnia

    return Uczelnia.objects.get_for_request(request)


def ukryte_statusy_podgladu(request, uczelnia=None):
    """Statusy korekty ukryte na poziomie „podglad" dla oglądającego.

    Ten sam kanał i ta sama bramka (``moze_wprowadzac_dane``) co strona
    szczegółów rekordu (``PracaViewMixin``) i globalne wyszukiwanie: osoby
    z uprawnieniami redakcyjnymi widzą wszystko, pozostali (także
    ``request=None``) — bez prac o ukrytych statusach. Zwraca listę (nie lazy
    queryset), memoizowaną na ``request`` na czas żądania.
    """
    from bpp.permissions import moze_wprowadzac_dane

    if request is not None:
        zapamietane = getattr(request, "_profil_ukryte_podglad", None)
        if zapamietane is not None:
            return zapamietane

    user = getattr(request, "user", None)
    if user is not None and moze_wprowadzac_dane(user):
        wynik = []
    else:
        if uczelnia is None:
            uczelnia = _uczelnia(request)
        if uczelnia is None:
            # Nieustalona uczelnia (multi-hosted) — fail-closed.
            from bpp.util.ukryte_statusy import statusy_ukryte_w_dowolnej_uczelni

            wynik = statusy_ukryte_w_dowolnej_uczelni("podglad")
        else:
            wynik = list(uczelnia.ukryte_statusy("podglad"))

    if request is not None:
        request._profil_ukryte_podglad = wynik
    return wynik


def _prace(autor, request=None):
    """Prace autora do sekcji profilu — PEŁNY dorobek autora.

    Celowo BEZ ``scope_rekord_do_uczelni``: profil (i eksport BibTeX/RIS,
    który bierze ten sam zbiór) pokazuje cały dorobek osoby, także prace
    afiliowane wyłącznie w innej uczelni tej samej instalacji (multi-hosted).
    Decyzja: zgłoszenie #930, opis w docs/administrator/ogolna.md.
    """
    from bpp.models import Rekord

    qs = Rekord.objects.prace_autora(autor)
    ukryte = ukryte_statusy_podgladu(request)
    if ukryte:
        qs = qs.exclude(status_korekty_id__in=ukryte)
    return qs


def _agreguj_po_latach(pary):
    """Zsumuj wartości w obrębie roku.

    ``pary`` — iterowalne ``(rok, wartosc)``. Pomija wiersze z ``None`` w roku
    lub wartości. Zwraca ``(dane, maks, suma)``, gdzie ``dane`` to posortowana
    rosnąco po roku lista ``(rok, suma_w_roku)``. Dla pustego wejścia zwraca
    ``([], 0, 0)``.
    """
    licznik = {}
    for rok, wartosc in pary:
        if rok is None or wartosc is None:
            continue
        licznik[rok] = licznik.get(rok, 0) + wartosc
    if not licznik:
        return [], 0, 0
    dane = sorted(licznik.items())
    wartosci = list(licznik.values())
    return dane, max(wartosci), sum(wartosci)


# Wykresy roczne domyślnie pokazują ostatnie N lat (węższy, czytelny wykres;
# pełna historia bywa zbyt szeroka). Por. spec §3.5 / kalibracja wizualna.
OKNO_LAT_WYKRESU = 10


def _ostatnie_lata(dane):
    """Ogranicz serię ``(rok, wartosc)`` (rosnąco po roku) do ostatnich
    ``OKNO_LAT_WYKRESU`` lat z danymi."""
    return dane[-OKNO_LAT_WYKRESU:]


# --- buildery sekcji -------------------------------------------------------


def _najlepsze_pk(autor, limit, request):
    return _lista(
        _prace(autor, request).filter(punkty_kbn__gt=0).order_by("-punkty_kbn", "-rok"),
        limit,
    )


def _najlepsze_if(autor, limit, request):
    return _lista(
        _prace(autor, request)
        .filter(impact_factor__gt=0)
        .order_by("-impact_factor", "-rok"),
        limit,
    )


def _najnowsze_artykuly(autor, limit, request):
    return _lista(
        _prace(autor, request)
        .filter(charakter_formalny__charakter_ogolny=const.CHARAKTER_OGOLNY_ARTYKUL)
        .order_by("-rok"),
        limit,
    )


def _najnowsze_zwarte(autor, limit, request):
    return _lista(
        _prace(autor, request)
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
    return _lista(_prace(autor, request).order_by("-ostatnio_zmieniony"), limit)


def _wybrane_publikacje(autor, limit, request):
    wybrane = list(
        autor.wybrane_publikacje.select_related("content_type").order_by("kolejnosc")
    )
    ukryte = set(ukryte_statusy_podgladu(request))
    prace = [
        w.publikacja
        for w in wybrane
        if w.publikacja is not None
        and getattr(w.publikacja, "status_korekty_id", None) not in ukryte
    ]
    return {"prace": prace} if prace else None


def _podsumowanie(autor, limit, request):
    # Liczba prac + łączny IF i punkty MNiSW. DISTINCT z ``id`` neutralizuje
    # duplikaty z joinu ``autorzy`` (por. docstring modułu); sumujemy w Pythonie.
    wiersze = (
        _prace(autor, request)
        .values_list("id", "rok", "impact_factor", "punkty_kbn")
        .distinct()
    )
    liczba = 0
    impact_factor = punkty_kbn = Decimal(0)
    lata = []
    for _id, rok, if_, pk in wiersze:
        liczba += 1
        impact_factor += if_ or 0
        punkty_kbn += pk or 0
        if rok is not None:
            lata.append(rok)
    if not liczba:
        return None
    return {
        "liczba": liczba,
        "impact_factor": impact_factor,
        "punkty_kbn": punkty_kbn,
        "rok_od": min(lata, default=None),
        "rok_do": max(lata, default=None),
    }


def _statystyki_charakter(autor, limit, request):
    pary = _prace(autor, request).values_list("id", "charakter_formalny__nazwa")
    licznik = Counter(nazwa for _id, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))
    return {"wiersze": wiersze, "suma": sum(licznik.values())}


def _wykres_lata(autor, limit, request):
    pary = _prace(autor, request).values_list("id", "rok")
    licznik = Counter(rok for _id, rok in pary if rok is not None)
    if not licznik:
        return None
    dane = _ostatnie_lata(sorted(licznik.items()))
    maks = max(w for _rok, w in dane)
    return {"dane": dane, "maks": maks, "etykieta": "prac"}


def _wykres_sumy_lata(autor, pole, etykieta, request):
    # Suma ``pole`` na rok. DISTINCT z włączonym ``id`` neutralizuje duplikaty
    # z joinu ``autorzy`` (rok/wartość są funkcją id).
    triple = _prace(autor, request).values_list("id", "rok", pole).distinct()
    dane, _maks, _suma = _agreguj_po_latach((rok, w) for _id, rok, w in triple)
    if not dane:
        return None
    dane = _ostatnie_lata(dane)
    # Auto-ukrycie liczone po OKNIE: same zera w ostatnich latach dają wykres
    # z płaskimi słupkami „0” — nie ma czego pokazywać (starsze wartości
    # i tak są poza wykresem).
    if not sum(w for _rok, w in dane):
        return None
    maks = max(w for _rok, w in dane)
    return {"dane": dane, "maks": maks, "etykieta": etykieta}


def _wykres_pk_lata(autor, limit, request):
    return _wykres_sumy_lata(autor, "punkty_kbn", "pkt", request)


def _wykres_if_lata(autor, limit, request):
    return _wykres_sumy_lata(autor, "impact_factor", "IF", request)


#: Wykresy pasa „Wykresy w latach” — (nazwa, builder), w kolejności na stronie.
_WYKRESY = (
    ("Publikacje w latach", _wykres_lata),
    ("Punkty MNiSW w latach", _wykres_pk_lata),
    ("Impact Factor w latach", _wykres_if_lata),
)


def _wykresy(autor, limit, request):
    # Wykresy stoją obok siebie w jednym pasie (równe wysokości z natury);
    # pusty wykres (np. autor bez IF) odpada, a pozostałe dzielą szerokość.
    wykresy = []
    for nazwa, builder in _WYKRESY:
        dane = builder(autor, limit, request)
        if dane is not None:
            wykresy.append({"nazwa": nazwa, "dane": dane})
    return {"wykresy": wykresy} if wykresy else None


def _mozna_pokazac_sloty(request):
    """Ta sama bramka co raport slotów autora (``pokazuj_raport_slotow_autor``
    + grupa „raporty — wyświetlanie” dla opcji „zalogowanym”). Bez uczelni —
    jak ``UczelniaSettingRequiredMixin`` — pokazujemy; bez requestu nie da się
    ocenić uprawnień, więc (poza „pokazuj zawsze”) ukrywamy."""
    from bpp.models import OpcjaWyswietlaniaField

    uczelnia = _uczelnia(request)
    if uczelnia is None:
        return True
    if request is None:
        return (
            uczelnia.pokazuj_raport_slotow_autor
            == OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
        )
    return uczelnia.sprawdz_uprawnienie("raport_slotow_autor", request)


def _punkty_lata(autor, limit, request):
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Query

    if not _mozna_pokazac_sloty(request):
        return None

    qs = Cache_Punktacja_Autora_Query.objects.filter(autor=autor)
    uczelnia = _uczelnia(request)
    ukryte = set(ukryte_statusy_podgladu(request))
    if uczelnia is not None:
        ukryte |= set(uczelnia.ukryte_statusy("sloty"))
    if ukryte:
        qs = qs.exclude(rekord__status_korekty_id__in=ukryte)

    wiersze = list(
        qs.values("rekord__rok")
        .annotate(pkd=Sum("pkdaut"), sloty=Sum("slot"))
        .order_by("rekord__rok")
    )
    return {"wiersze": wiersze} if wiersze else None


def _dyscypliny(autor, limit, request):
    from bpp.models import Autorzy

    pary = (
        Autorzy.objects.filter(autor=autor)
        .exclude(dyscyplina_naukowa=None)
        .exclude(rekord__status_korekty_id__in=ukryte_statusy_podgladu(request))
        .values_list("rekord_id", "dyscyplina_naukowa__nazwa")
        .distinct()
    )
    licznik = Counter(nazwa for _r, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))
    return {"wiersze": wiersze, "suma": sum(licznik.values())}


def _zrodla(autor, limit, request):
    pary = (
        _prace(autor, request).exclude(zrodlo=None).values_list("id", "zrodlo__nazwa")
    )
    licznik = Counter(nazwa for _id, nazwa in pary if nazwa)
    if not licznik:
        return None
    wiersze = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return {"wiersze": wiersze}


def _wspolautorzy(autor, limit, request):
    from powiazania_autorow.models import AuthorConnection

    polaczenia = (
        AuthorConnection.objects.filter(
            (Q(primary_author=autor) & Q(secondary_author__pokazuj=True))
            | (Q(secondary_author=autor) & Q(primary_author__pokazuj=True))
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
    KLUCZ_PODSUMOWANIE: _podsumowanie,
    KLUCZ_NAJLEPSZE_PK: _najlepsze_pk,
    KLUCZ_NAJLEPSZE_IF: _najlepsze_if,
    KLUCZ_NAJNOWSZE_ARTYKULY: _najnowsze_artykuly,
    KLUCZ_NAJNOWSZE_ZWARTE: _najnowsze_zwarte,
    KLUCZ_OSTATNIO_EDYTOWANE: _ostatnio_edytowane,
    KLUCZ_WYBRANE_PUBLIKACJE: _wybrane_publikacje,
    KLUCZ_STATYSTYKI_CHARAKTER: _statystyki_charakter,
    KLUCZ_WYKRESY: _wykresy,
    KLUCZ_PUNKTY_LATA: _punkty_lata,
    KLUCZ_DYSCYPLINY: _dyscypliny,
    KLUCZ_ZRODLA: _zrodla,
    KLUCZ_WSPOLAUTORZY: _wspolautorzy,
}


def przygotuj_sekcje(autor, uczelnia=None, request=None):
    """Zwróć widoczne sekcje w kolejności renderowania, z danymi.

    Układ pobierany jest z ``uczelnia`` (``rozwiaz_uklad``), dane — z
    ``autor``. Każdy element to ``{"klucz", "nazwa", "template", "dane",
    "szerokosc", "karta"}`` (``dane`` jest ``None`` dla sekcji
    tylko-szablonowych — partial czyta wtedy ``autor`` itd. z kontekstu).

    Reguły pomijania:
    - sekcja TYLKO-SZABLONOWA (``template_only``) jest ZAWSZE dołączana —
      partial sam się bramkuje (``{% if %}``), a pusty wynik odrzuca dopiero
      tag ``pasy_profilu`` (przed parowaniem w pasy);
    - sekcja DATA-DRIVEN jest pomijana, gdy jej builder zwrócił ``None`` (pusta)
      lub gdy buildera (jeszcze) nie ma.
    """
    from bpp.profil_autora import rozwiaz_uklad

    wynik = []
    for s in rozwiaz_uklad(uczelnia):
        if s["template_only"]:
            dane = None
        else:
            builder = _BUILDERY.get(s["klucz"])
            if builder is None:
                continue
            dane = builder(autor, s["limit"], request)
            if dane is None:
                continue
        wynik.append(
            {
                "klucz": s["klucz"],
                "nazwa": s["nazwa"],
                "template": s["template"],
                "dane": dane,
                "szerokosc": s["szerokosc"],
                "karta": s["karta"],
                "elastyczna": s["elastyczna"],
            }
        )
    return wynik
