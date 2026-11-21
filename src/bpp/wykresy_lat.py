"""Wykresy „w latach” dla stron jednostki, źródła i wydawcy.

Ten sam kształt danych i ten sam szablon co pas wykresów na stronie autora
(``browse/autor_sekcje/wykresy.html``): lista ``{nazwa, dane, raport}``,
gdzie ``dane`` = ``{dane: [(rok, wartosc)], maks, etykieta, miejsca}``
(``miejsca`` — liczba miejsc po przecinku do wyświetlenia). Różnica:
tu wszystko liczy JEDNO zapytanie agregujące w SQL — jednostka-wydział
potrafi mieć dziesiątki tysięcy prac, więc nie ciągniemy wierszy do Pythona
(strona autora robi to w ``profil_autora_dane``, bo zbiory są małe).
"""

from django.db.models import Count, Sum

from bpp.profil_autora_dane import OKNO_LAT_WYKRESU, ukryte_statusy_podgladu

#: Liczba miejsc po przecinku na wykresach: liczby prac i punkty — całkowite,
#: IF — dwa miejsca (szablon formatuje ``floatformat``, wysokości słupków
#: liczy z surowych wartości).
MIEJSCA_LICZBA = 0
MIEJSCA_IF = 2

#: (nazwa, klucz agregatu, etykieta wartości, typ raportu po kliknięciu).
#: Wykresy punktowe otwierają raport „tabela” (kolumny IF/PK), jak u autora.
_WYKRESY = (
    ("Publikacje w latach", "liczba", "prac", None),
    ("Punkty MNiSW w latach", "punkty", "pkt", "table"),
    ("Impact Factor w latach", "impact", "IF", "table"),
)

#: Strona źródła: suma punktów prac rośnie z ich liczbą, więc zamiast niej
#: pokazujemy punktację samego czasopisma z ``Punktacja_Zrodla`` (klucz =
#: pole modelu). Klik w rok — jak wyżej, prace źródła z tego roku.
_WYKRESY_PUNKTACJI_ZRODLA = (
    ("Punkty MNiSW czasopisma w latach", "punkty_kbn", "pkt", "table"),
    ("Impact Factor czasopisma w latach", "impact_factor", "IF", "table"),
)


def _miejsca(etykieta):
    return MIEJSCA_IF if etykieta == "IF" else MIEJSCA_LICZBA


def _seria(wiersze, klucz, etykieta):
    dane = [(w["rok"], w[klucz] or 0) for w in wiersze if w["rok"] is not None]
    dane = dane[-OKNO_LAT_WYKRESU:]
    # Same zera w oknie (np. źródło bez IF) — wykres byłby płaską kreską.
    if not dane or not any(wartosc for _rok, wartosc in dane):
        return None
    return {
        "dane": dane,
        "maks": max(wartosc for _rok, wartosc in dane),
        "etykieta": etykieta,
        "miejsca": _miejsca(etykieta),
    }


def _zbuduj(wiersze, definicje):
    wykresy = []
    for nazwa, klucz, etykieta, raport in definicje:
        dane = _seria(wiersze, klucz, etykieta)
        if dane is not None:
            wykresy.append({"nazwa": nazwa, "dane": dane, "raport": raport})
    return wykresy


def wykresy_w_latach(rekordy, request=None, definicje=_WYKRESY):
    """``rekordy`` — queryset ``Rekord`` (np. ``prace_jednostki``). Zwraca
    listę wykresów do ``wykresy.html`` (pustą, gdy nie ma czego pokazać)."""
    from bpp.models import Rekord

    ukryte = ukryte_statusy_podgladu(request)
    if ukryte:
        rekordy = rekordy.exclude(status_korekty_id__in=ukryte)

    # ``pk__in`` zamiast agregacji wprost na ``rekordy``: querysety prac
    # jednostki mają JOIN po autorach + DISTINCT — suma punktów liczyłaby
    # pracę raz na każdego autora z jednostki.
    wiersze = list(
        Rekord.objects.filter(pk__in=rekordy.values("pk"))
        .values("rok")
        .annotate(
            liczba=Count("pk"),
            punkty=Sum("punkty_kbn"),
            impact=Sum("impact_factor"),
        )
        .order_by("rok")
    )

    return _zbuduj(wiersze, definicje)


def wykresy_zrodla(zrodlo, request=None):
    """Wykresy strony źródła: liczba prac w latach (z rekordów) oraz punktacja
    czasopisma w latach (``Punktacja_Zrodla``) zamiast sum punktów prac."""
    from bpp.models import Punktacja_Zrodla, Rekord

    wykresy = wykresy_w_latach(
        Rekord.objects.filter(zrodlo=zrodlo), request, definicje=_WYKRESY[:1]
    )
    wiersze = list(
        Punktacja_Zrodla.objects.filter(zrodlo=zrodlo)
        .order_by("rok")
        .values("rok", *(klucz for _n, klucz, _e, _r in _WYKRESY_PUNKTACJI_ZRODLA))
    )
    return wykresy + _zbuduj(wiersze, _WYKRESY_PUNKTACJI_ZRODLA)
