"""Sugerowanie punktacji ministerialnej (punkty_kbn).

Jedno źródło prawdy o progach zwartych — współdzielone przez importer
publikacji (nowy krok „Punktacja") i komendę ``ustaw_zwrotnie_punkty_zwartych``.
"""

import enum
from dataclasses import dataclass
from decimal import Decimal


class RodzajBraku(enum.Enum):
    """Dlaczego nie da się zaproponować punktów.

    Rozróżnia anomalię DANYCH (brak wydawcy/roku/autorstwa/punktacji źródła) od
    luki w logice (nieobsłużona kombinacja typu) — komenda mapuje to na
    skip+raport vs twardy ``NotImplementedError``.
    """

    BRAK_DANYCH_ZRODLA = "brak_danych_zrodla"
    BRAK_ROKU = "brak_roku"
    BRAK_WYDAWCY = "brak_wydawcy"
    BRAK_AUTORSTWA = "brak_autorstwa"
    NIEOBSLUZONA_KOMBINACJA = "nieobsluzona_kombinacja"


@dataclass
class SugestiaPunktacji:
    punkty: Decimal | None
    podstawa: str = ""
    rodzaj_braku: RodzajBraku | None = None
    powod_braku: str | None = None


# PROGI_ZWARTE[poziom] — poziom 0 (spoza wykazu) / I / II.
PROGI_ZWARTE = [
    {"KS": Decimal(20), "RED": Decimal(5), "ROZ": Decimal(5)},
    {"KS": Decimal(80), "RED": Decimal(20), "ROZ": Decimal(20)},
    {"KS": Decimal(200), "RED": Decimal(100), "ROZ": Decimal(50)},
]

_OPIS_POZIOMU = {0: "spoza wykazu", 1: "I", 2: "II"}


def zaproponuj_punkty_zwarte(*, poziom, ksiazka, rozdzial, autorstwo, redakcja):
    """Zaproponuj punkty_kbn dla wydawnictwa zwartego na bazie prymitywów.

    ``poziom`` = wynik ``Wydawca.get_tier(rok)`` (-1/None → 0 „spoza wykazu").
    ``ksiazka``/``rozdzial`` z ``charakter_sloty``; ``autorstwo``/``redakcja`` z
    ról autorów. Nie dotyka bazy, nie rzuca — braki zwraca w ``rodzaj_braku``.
    """
    if poziom in (-1, None):
        poziom = 0
    progi = PROGI_ZWARTE[poziom]
    opis = _OPIS_POZIOMU[poziom]

    if not autorstwo and not redakcja:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_AUTORSTWA,
            powod_braku="Brak punktowalnego autorstwa/redakcji",
        )
    if ksiazka and rozdzial:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.NIEOBSLUZONA_KOMBINACJA,
            powod_braku="Rekord jest jednocześnie książką i rozdziałem",
        )
    if ksiazka and autorstwo:
        return SugestiaPunktacji(progi["KS"], f"Wydawca poziom {opis} — monografia")
    if ksiazka and redakcja:
        return SugestiaPunktacji(progi["RED"], f"Wydawca poziom {opis} — redakcja")
    if rozdzial and autorstwo:
        return SugestiaPunktacji(progi["ROZ"], f"Wydawca poziom {opis} — rozdział")
    return SugestiaPunktacji(
        punkty=None,
        rodzaj_braku=RodzajBraku.NIEOBSLUZONA_KOMBINACJA,
        powod_braku=(
            f"Nieobsłużona kombinacja: ksiazka={ksiazka} rozdzial={rozdzial} "
            f"autorstwo={autorstwo} redakcja={redakcja}"
        ),
    )


def zaproponuj_punkty_ciagle(zrodlo, rok):
    """Zaproponuj punkty_kbn dla wydawnictwa ciągłego z Punktacja_Zrodla.

    Bez PBN-owego fallbacku „5 pkt" — importer pokazuje uczciwe „brak danych".
    """
    from bpp.models import Punktacja_Zrodla

    if not rok:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_ROKU,
            powod_braku="Brak roku publikacji — nie można dobrać punktacji źródła",
        )
    try:
        pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=rok)
    except Punktacja_Zrodla.DoesNotExist:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_DANYCH_ZRODLA,
            powod_braku=f"Brak punktacji źródła „{zrodlo}” za {rok}",
        )
    return SugestiaPunktacji(pz.punkty_kbn, f"Punktacja źródła {rok}")
