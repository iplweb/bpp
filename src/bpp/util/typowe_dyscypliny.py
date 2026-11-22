"""„Typowe dyscypliny uczelni" — podpowiedź, gdy autor nie ma przypisanej
dyscypliny na rok publikacji (FD#620).

Typowe = dyscypliny najczęściej przypisywane autorom w pracach z ostatnich
lat (rok bieżący i ``LATA_WSTECZ`` poprzednich), liczone po rekordach
``*_Autor`` (wydawnictwa ciągłe, zwarte, patenty), osobno dla każdej uczelni
(po jednostce, w której autor jest przypisany do pracy).

Wynik trzymamy w domyślnym cache (Redis w produkcji) i przeliczamy raz na
dobę zadaniem Celery beat ``bpp.tasks.odswiez_typowe_dyscypliny``. Gdy cache
jest pusty (świeży start, inne środowisko, DummyCache w dev/testach), liczymy
na żądanie — to kilka zapytań GROUP BY po indeksowanych kolumnach. Gdy
w bazie nie ma jeszcze żadnych prac z dyscyplinami, podpowiadamy wszystkie
widoczne dyscypliny.
"""

from collections import Counter
from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

CACHE_KEY = "bpp:typowe_dyscypliny:v1"

#: Doba + zapas: zadanie beat odświeża wartość, zanim ta wygaśnie.
CACHE_TIMEOUT = 26 * 60 * 60

#: Ile lat wstecz (poza bieżącym) bierzemy pod uwagę.
LATA_WSTECZ = 2


@dataclass(frozen=True)
class TypoweDyscypliny:
    #: Lista ``Dyscyplina_Naukowa`` — od najczęściej używanej.
    dyscypliny: list
    rok_od: int
    rok_do: int
    #: ``True`` — brak danych o typowych, ``dyscypliny`` to wszystkie
    #: widoczne dyscypliny (alfabetycznie).
    wszystkie: bool


def _modele_autorow():
    from bpp.models import (
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    return (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)


def policz_typowe_dyscypliny(rok_do=None):
    """Policz (bez cache) typowe dyscypliny dla każdej uczelni.

    Zwraca słownik gotowy do zapisania w cache::

        {"rok_od": 2024, "rok_do": 2026,
         "uczelnie": {"<uczelnia_id>": [dyscyplina_id, ...]},
         "wszystkie_uczelnie": [dyscyplina_id, ...]}

    Listy są posortowane malejąco po liczbie przypisań (remis: po id).
    """
    if rok_do is None:
        rok_do = timezone.now().year
    rok_od = rok_do - LATA_WSTECZ

    per_uczelnia = {}
    razem = Counter()
    for model in _modele_autorow():
        wiersze = (
            model.objects.filter(
                rekord__rok__gte=rok_od,
                rekord__rok__lte=rok_do,
                dyscyplina_naukowa__isnull=False,
                dyscyplina_naukowa__widoczna=True,
            )
            .values_list("jednostka__uczelnia_id", "dyscyplina_naukowa_id")
            .annotate(n=Count("pk"))
            .order_by()
        )
        for uczelnia_id, dyscyplina_id, n in wiersze:
            razem[dyscyplina_id] += n
            if uczelnia_id is not None:
                per_uczelnia.setdefault(uczelnia_id, Counter())[dyscyplina_id] += n

    def _posortuj(licznik):
        return [d for d, _n in sorted(licznik.items(), key=lambda x: (-x[1], x[0]))]

    return {
        "rok_od": rok_od,
        "rok_do": rok_do,
        "uczelnie": {str(k): _posortuj(v) for k, v in per_uczelnia.items()},
        "wszystkie_uczelnie": _posortuj(razem),
    }


def odswiez_typowe_dyscypliny():
    """Przelicz typowe dyscypliny i zapisz w cache. Zwraca policzone dane."""
    dane = policz_typowe_dyscypliny()
    cache.set(CACHE_KEY, dane, CACHE_TIMEOUT)
    return dane


def _dane():
    dane = cache.get(CACHE_KEY)
    if dane is None:
        dane = odswiez_typowe_dyscypliny()
    return dane


def typowe_dyscypliny(uczelnia=None):
    """Typowe dyscypliny dla ``uczelnia`` (``None`` — dla całej bazy).

    Uczelnia bez własnych danych dostaje listę z całej bazy; baza bez
    żadnych prac z dyscyplinami — wszystkie widoczne dyscypliny.
    """
    from bpp.models import Dyscyplina_Naukowa

    dane = _dane()
    ids = []
    if uczelnia is not None:
        ids = dane["uczelnie"].get(str(uczelnia.pk), [])
    if not ids:
        ids = dane["wszystkie_uczelnie"]

    if ids:
        po_id = Dyscyplina_Naukowa.objects.filter(pk__in=ids, widoczna=True).in_bulk()
        dyscypliny = [po_id[pk] for pk in ids if pk in po_id]
        if dyscypliny:
            return TypoweDyscypliny(
                dyscypliny=dyscypliny,
                rok_od=dane["rok_od"],
                rok_do=dane["rok_do"],
                wszystkie=False,
            )

    return TypoweDyscypliny(
        dyscypliny=list(
            Dyscyplina_Naukowa.objects.filter(widoczna=True).order_by("nazwa")
        ),
        rok_od=dane["rok_od"],
        rok_do=dane["rok_do"],
        wszystkie=True,
    )


ZRODLO_ROK_AUTORA = "rok_autora"
ZRODLO_TYPOWE = "typowe"
ZRODLO_WSZYSTKIE = "wszystkie"


@dataclass(frozen=True)
class PropozycjaDyscyplin:
    """Dyscypliny do wyboru dla autora bez przypisania na rok pracy."""

    dyscypliny: list
    #: ``ZRODLO_ROK_AUTORA`` — dyscypliny autora z roku ``rok_zrodla``
    #: (najbliższy wcześniejszy rok z przypisaniem); ``ZRODLO_TYPOWE`` —
    #: typowe dla uczelni (prace z lat ``rok_od``–``rok_do``);
    #: ``ZRODLO_WSZYSTKIE`` — brak danych, wszystkie widoczne dyscypliny.
    zrodlo: str
    rok_zrodla: int | None = None
    rok_od: int | None = None
    rok_do: int | None = None

    def opis_zrodla(self):
        if self.zrodlo == ZRODLO_ROK_AUTORA:
            return f"dyscypliny autora z roku {self.rok_zrodla}"
        if self.zrodlo == ZRODLO_TYPOWE:
            return f"typowe dla uczelni (prace z lat {self.rok_od}–{self.rok_do})"
        return "wszystkie dyscypliny"


def propozycja_dla_autora_bez_przypisania(autor_id, rok, uczelnia=None):
    """Dyscypliny do wyboru dla autora, który nie ma przypisania na ``rok``.

    * Autor miał przypisanie we wcześniejszym roku — jego dyscyplina
      (i subdyscyplina) z NAJBLIŻSZEGO wcześniejszego roku z przypisaniem
      (zwykle ``rok - 1``).
    * Autor nie miał przypisania nigdy wcześniej — typowe dla uczelni
      (``typowe_dyscypliny``), a bez danych — wszystkie dyscypliny.

    Wołający sam sprawdza, że autor nie ma przypisania na ``rok``.
    """
    from bpp.models import Autor_Dyscyplina

    poprzednie = (
        Autor_Dyscyplina.all_objects.filter(autor_id=autor_id, rok__lt=rok)
        .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
        .order_by("-rok")
        .first()
    )
    if poprzednie is not None:
        dyscypliny = [poprzednie.dyscyplina_naukowa]
        if poprzednie.subdyscyplina_naukowa_id is not None:
            dyscypliny.append(poprzednie.subdyscyplina_naukowa)
        return PropozycjaDyscyplin(
            dyscypliny=dyscypliny,
            zrodlo=ZRODLO_ROK_AUTORA,
            rok_zrodla=poprzednie.rok,
        )

    typowe = typowe_dyscypliny(uczelnia)
    return PropozycjaDyscyplin(
        dyscypliny=typowe.dyscypliny,
        zrodlo=ZRODLO_WSZYSTKIE if typowe.wszystkie else ZRODLO_TYPOWE,
        rok_od=typowe.rok_od,
        rok_do=typowe.rok_do,
    )
