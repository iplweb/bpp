"""Wykresy „w latach” dla stron jednostki i źródła.

Ten sam kształt danych i ten sam szablon co pas wykresów na stronie autora
(``browse/autor_sekcje/wykresy.html``): lista ``{nazwa, dane, raport}``,
gdzie ``dane`` = ``{dane: [(rok, wartosc)], maks, etykieta}``. Różnica:
tu wszystko liczy JEDNO zapytanie agregujące w SQL — jednostka-wydział
potrafi mieć dziesiątki tysięcy prac, więc nie ciągniemy wierszy do Pythona
(strona autora robi to w ``profil_autora_dane``, bo zbiory są małe).
"""

from django.db.models import Count, Sum

from bpp.profil_autora_dane import OKNO_LAT_WYKRESU, ukryte_statusy_podgladu

#: (nazwa, klucz agregatu, etykieta wartości, typ raportu po kliknięciu).
#: Wykresy punktowe otwierają raport „tabela” (kolumny IF/PK), jak u autora.
_WYKRESY = (
    ("Publikacje w latach", "liczba", "prac", None),
    ("Punkty MNiSW w latach", "punkty", "pkt", "table"),
    ("Impact Factor w latach", "impact", "IF", "table"),
)


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
    }


def wykresy_w_latach(rekordy, request=None):
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

    wykresy = []
    for nazwa, klucz, etykieta, raport in _WYKRESY:
        dane = _seria(wiersze, klucz, etykieta)
        if dane is not None:
            wykresy.append({"nazwa": nazwa, "dane": dane, "raport": raport})
    return wykresy
