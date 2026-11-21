"""Ile punktów w bieżącej ewaluacji daje publikacja w danym źródle lub
u danego wydawcy — dla strony źródła i strony wydawcy.

Okres: ``const.PBN_AKTUALNA_EWALUACJA_START``–``STOP`` (ten sam, co panel
„Dyscypliny naukowe w ewaluacji” na stronie źródła).

* Źródło: punktacja czasopisma z ``Punktacja_Zrodla`` za lata okresu; artykuł
  jednego autora dostaje pełną punktację czasopisma.
* Wydawca: poziom z ``Poziom_Wydawcy`` (brak wpisu albo „nieokreślono” =
  spoza wykazu) i progi monografii / rozdziału / redakcji z
  ``punktacja_sugestia.PROGI_ZWARTE`` (jedno źródło prawdy o progach).
"""

from bpp import const
from bpp.punktacja_sugestia import PROGI_ZWARTE

NAZWA_POZIOMU = {0: "spoza wykazu", 1: "poziom I", 2: "poziom II"}


def _lata():
    return list(
        range(const.PBN_AKTUALNA_EWALUACJA_START, const.PBN_AKTUALNA_EWALUACJA_STOP + 1)
    )


def _okres():
    return {
        "od": const.PBN_AKTUALNA_EWALUACJA_START,
        "do": const.PBN_AKTUALNA_EWALUACJA_STOP,
    }


def punkty_ewaluacji_zrodla(zrodlo):
    """``{"od", "do", "lata": [{"rok", "punkty"}], "aktualne": {...} | None}``.

    ``lata`` — tylko lata okresu z punktacją; ``aktualne`` — najnowszy z nich
    (punkty za artykuł jednego autora). Jedno zapytanie."""
    from bpp.models import Punktacja_Zrodla

    lata = [
        {"rok": rok, "punkty": punkty}
        for rok, punkty in Punktacja_Zrodla.objects.filter(
            zrodlo=zrodlo, rok__in=_lata(), punkty_kbn__gt=0
        )
        .order_by("rok")
        .values_list("rok", "punkty_kbn")
    ]
    return {**_okres(), "lata": lata, "aktualne": lata[-1] if lata else None}


def _punkty_zwarte(poziom):
    progi = PROGI_ZWARTE[poziom]
    return {
        "monografia": progi["KS"],
        "rozdzial": progi["ROZ"],
        "redakcja": progi["RED"],
    }


def punkty_ewaluacji_wydawcy(wydawca):
    """``{"od", "do", "lata": [{"rok", "poziom", "nazwa"}], "aktualne": {...}}``.

    ``lata`` — każdy rok okresu (brak wpisu = spoza wykazu); ``aktualne`` —
    najnowszy rok z wpisem w wykazie (albo ostatni rok okresu, gdy wydawcy
    w wykazie nie ma) z punktami za monografię, rozdział i redakcję
    jednego autora. Liczone dla wydawcy głównego (aliasy dzielą poziom)."""
    toplevel = wydawca.get_toplevel()
    wpisy = dict(
        toplevel.poziom_wydawcy_set.filter(rok__in=_lata()).values_list("rok", "poziom")
    )

    lata = []
    for rok in _lata():
        poziom = wpisy.get(rok) or 0
        lata.append({"rok": rok, "poziom": poziom, "nazwa": NAZWA_POZIOMU[poziom]})

    w_wykazie = [w for w in lata if w["poziom"]]
    aktualne = dict(w_wykazie[-1] if w_wykazie else lata[-1])
    aktualne.update(_punkty_zwarte(aktualne["poziom"]))
    return {
        **_okres(),
        "lata": lata,
        "aktualne": aktualne,
        "w_wykazie": bool(w_wykazie),
    }
