"""Strona wydawcy: podział prac na książki, rozdziały i resztę.

Kategoria to charakter ogólny charakteru formalnego (``charakter_ogolny``) —
to samo kryterium co pole multiseeka „Charakter formalny ogólny”
(``CharakterOgolnyQueryObject``), więc liczba na stronie zgadza się z liczbą
wyników po kliknięciu. Liczy JEDNO zapytanie agregujące (rok × kategoria).
"""

from django.db.models import Count, F

from bpp import const
from bpp.profil_autora_dane import OKNO_LAT_WYKRESU, ukryte_statusy_podgladu

#: (kod charakteru ogólnego, wartość pola multiseeka, formy liczebnika
#: (1, 2–4, 5+), nazwa wykresu w latach albo None — bez osobnego wykresu).
KATEGORIE = (
    (
        const.CHARAKTER_OGOLNY_KSIAZKA,
        "książka",
        ("książka", "książki", "książek"),
        "Książki w latach",
    ),
    (
        const.CHARAKTER_OGOLNY_ROZDZIAL,
        "rozdział",
        ("rozdział", "rozdziały", "rozdziałów"),
        "Rozdziały w latach",
    ),
    (
        const.CHARAKTER_OGOLNY_ARTYKUL,
        "artykuł",
        ("artykuł", "artykuły", "artykułów"),
        None,
    ),
    (
        const.CHARAKTER_OGOLNY_INNE,
        "inne",
        ("inna praca", "inne prace", "innych prac"),
        None,
    ),
)

#: Charakter ogólny rekordu (przez charakter formalny).
_KOD = F("charakter_formalny__charakter_ogolny")


def _forma(liczba, formy):
    jedna, kilka, wiele = formy
    if liczba == 1:
        return jedna
    if liczba % 10 in (2, 3, 4) and liczba % 100 not in (12, 13, 14):
        return kilka
    return wiele


def _wiersze(prace, request):
    from bpp.models import Rekord

    ukryte = ukryte_statusy_podgladu(request)
    if ukryte:
        prace = prace.exclude(status_korekty_id__in=ukryte)
    return list(
        Rekord.objects.filter(pk__in=prace.values("pk"))
        .values("rok", kod=_KOD)
        .annotate(liczba=Count("pk"))
        .order_by("rok")
    )


def podzial_wydawcy(prace, request=None):
    """Zwraca ``{"podzial": [...], "wykresy_kategorii": [...]}``.

    ``podzial`` — niepuste kategorie w stałej kolejności (książki, rozdziały,
    artykuły, inne): ``{"wartosc", "liczba", "opis"}``, gdzie ``wartosc`` idzie
    do BuildSearch jako ``charakter_ogolny``, a ``opis`` to np. „12 książek”.

    ``wykresy_kategorii`` — wykresy „Książki w latach” / „Rozdziały w latach”
    w kształcie ``wykresy.html``; ``pola`` dokłada do kliknięcia w rok filtr
    kategorii (klik daje książki z danego roku, nie wszystkie prace).
    """
    wiersze = _wiersze(prace, request)

    sumy = {}
    lata = {}
    for w in wiersze:
        sumy[w["kod"]] = sumy.get(w["kod"], 0) + w["liczba"]
        if w["rok"] is not None:
            lata.setdefault(w["kod"], []).append((w["rok"], w["liczba"]))

    podzial = []
    wykresy = []
    for kod, wartosc, formy, nazwa_wykresu in KATEGORIE:
        liczba = sumy.get(kod, 0)
        if not liczba:
            continue
        podzial.append(
            {
                "wartosc": wartosc,
                "liczba": liczba,
                "opis": f"{liczba} {_forma(liczba, formy)}",
            }
        )
        dane = lata.get(kod, [])[-OKNO_LAT_WYKRESU:]
        if nazwa_wykresu and dane:
            wykresy.append(
                {
                    "nazwa": nazwa_wykresu,
                    "dane": {
                        "dane": dane,
                        "maks": max(wartosc_roku for _rok, wartosc_roku in dane),
                        "etykieta": formy[2],
                        "miejsca": 0,
                    },
                    "raport": None,
                    "pola": [("charakter_ogolny", wartosc)],
                }
            )
    return {"podzial": podzial, "wykresy_kategorii": wykresy}
