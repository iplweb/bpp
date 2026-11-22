"""Ile punktów w bieżącej ewaluacji daje publikacja w danym źródle lub
u danego wydawcy — dla strony źródła i strony wydawcy.

Okresy: z tabeli okresów ewaluacji (``ewaluacja_common.OkresEwaluacji``) —
``okresy_ewaluacji_strony`` daje bieżący okres (rozwinięty na stronie) i
poprzednie (zwinięte). Pojedyncze funkcje bez podanych lat liczą okres
``const.PBN_AKTUALNA_EWALUACJA_START``–``STOP``.

* Źródło: punktacja czasopisma z ``Punktacja_Zrodla`` za lata okresu; artykuł
  jednego autora dostaje pełną punktację czasopisma.
* Wydawca: poziom z ``Poziom_Wydawcy`` (brak wpisu albo „nieokreślono” =
  spoza wykazu) i progi monografii / rozdziału / redakcji z
  ``punktacja_sugestia.PROGI_ZWARTE`` (jedno źródło prawdy o progach).
"""

from bpp import const
from bpp.punktacja_sugestia import PROGI_ZWARTE

NAZWA_POZIOMU = {0: "spoza wykazu", 1: "poziom I", 2: "poziom II"}


def _zakres(od, do):
    if od is None or do is None:
        return const.PBN_AKTUALNA_EWALUACJA_START, const.PBN_AKTUALNA_EWALUACJA_STOP
    return od, do


def _lata(od=None, do=None):
    od, do = _zakres(od, do)
    return list(range(od, do + 1))


def _okres(od=None, do=None):
    od, do = _zakres(od, do)
    return {"od": od, "do": do}


def punkty_ewaluacji_zrodla(zrodlo, od=None, do=None):
    """``{"od", "do", "lata": [{"rok", "punkty"}], "aktualne": {...} | None}``.

    ``lata`` — tylko lata okresu z punktacją; ``aktualne`` — najnowszy z nich
    (punkty za artykuł jednego autora). Jedno zapytanie."""
    from bpp.models import Punktacja_Zrodla

    lata = [
        {"rok": rok, "punkty": punkty}
        for rok, punkty in Punktacja_Zrodla.objects.filter(
            zrodlo=zrodlo, rok__in=_lata(od, do), punkty_kbn__gt=0
        )
        .order_by("rok")
        .values_list("rok", "punkty_kbn")
    ]
    wynik = {**_okres(od, do), "lata": lata, "aktualne": lata[-1] if lata else None}
    if not lata:
        # Pusto, bo czasopisma nie ma w wykazie — czy wykazu za ten okres
        # jeszcze w ogóle nie wczytano (np. nowy okres ewaluacji)?
        wynik["brak_wykazu"] = not Punktacja_Zrodla.objects.filter(
            rok__in=_lata(od, do), punkty_kbn__gt=0
        ).exists()
    return wynik


def _punkty_zwarte(poziom):
    progi = PROGI_ZWARTE[poziom]
    return {
        "monografia": progi["KS"],
        "rozdzial": progi["ROZ"],
        "redakcja": progi["RED"],
    }


def punkty_ewaluacji_wydawcy(wydawca, od=None, do=None):
    """``{"od", "do", "lata": [{"rok", "poziom", "nazwa"}], "aktualne": {...}}``.

    ``lata`` — każdy rok okresu (brak wpisu = spoza wykazu); ``aktualne`` —
    najnowszy rok z wpisem w wykazie (albo ostatni rok okresu, gdy wydawcy
    w wykazie nie ma) z punktami za monografię, rozdział i redakcję
    jednego autora. Liczone dla wydawcy głównego (aliasy dzielą poziom)."""
    from bpp.models.wydawca import Poziom_Wydawcy

    toplevel = wydawca.get_toplevel()
    wpisy = dict(
        toplevel.poziom_wydawcy_set.filter(rok__in=_lata(od, do)).values_list(
            "rok", "poziom"
        )
    )

    lata = []
    for rok in _lata(od, do):
        poziom = wpisy.get(rok) or 0
        lata.append({"rok": rok, "poziom": poziom, "nazwa": NAZWA_POZIOMU[poziom]})

    w_wykazie = [w for w in lata if w["poziom"]]
    aktualne = dict(w_wykazie[-1] if w_wykazie else lata[-1])
    aktualne.update(_punkty_zwarte(aktualne["poziom"]))
    wynik = {
        **_okres(od, do),
        "lata": lata,
        "aktualne": aktualne,
        "w_wykazie": bool(w_wykazie),
    }
    if not w_wykazie:
        # „Spoza wykazu” tylko, gdy wykaz za ten okres w ogóle jest w bazie.
        wynik["brak_wykazu"] = not Poziom_Wydawcy.objects.filter(
            rok__in=_lata(od, do), poziom__gt=0
        ).exists()
    return wynik


def okresy_ewaluacji_strony(funkcja, obiekt):
    """Okresy do ramki „Ewaluacja” na stronie źródła/wydawcy.

    ``[{"dane": funkcja(obiekt, od, do), "biezacy": bool}]`` — najpierw bieżący
    okres (zawierający bieżący rok, ``okres_domyslny``), potem poprzednie od
    najnowszego. Przyszłych okresów nie pokazujemy. Bez tabeli okresów —
    jeden okres ze stałych ``const``.
    """
    from ewaluacja_common.models import OkresEwaluacji
    from ewaluacja_common.okres import okres_domyslny

    biezacy = okres_domyslny()
    if biezacy is None:
        return [{"dane": funkcja(obiekt), "biezacy": True}]
    poprzednie = OkresEwaluacji.objects.filter(rok_od__lt=biezacy.rok_od).order_by(
        "-rok_od"
    )
    return [
        {"dane": funkcja(obiekt, biezacy.rok_od, biezacy.rok_do), "biezacy": True}
    ] + [
        {"dane": funkcja(obiekt, o.rok_od, o.rok_do), "biezacy": False}
        for o in poprzednie
    ]
