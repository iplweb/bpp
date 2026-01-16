"""Journal/source handling for PBN importer."""

from django.db import DataError
from django.db.models import Subquery

from bpp import const
from bpp.models import (
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Rodzaj_Zrodla,
    Zrodlo,
)
from bpp.util import pbar
from pbn_api.models import Journal
from pbn_integrator.utils import integruj_zrodla


def dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache):
    """Process single journal - re-entrant, can be interrupted."""
    assert pbn_journal.rekord_w_bpp() is None

    cv = pbn_journal.current_version["object"]

    # Create Zrodlo
    zrodlo = Zrodlo.objects.create(
        nazwa=cv.get("title") or "",
        skrot=cv.get("title") or "",
        issn=cv.get("issn") or "",
        e_issn=cv.get("eissn") or "",
        pbn_uid=pbn_journal,
        rodzaj=rodzaj_periodyk,
    )

    # Bulk create points
    punktacje = [
        Punktacja_Zrodla(zrodlo=zrodlo, rok=rok, punkty_kbn=value.get("points"))
        for rok, value in cv.get("points", {}).items()
        if value.get("accepted")
    ]
    if punktacje:
        Punktacja_Zrodla.objects.bulk_create(punktacje, ignore_conflicts=True)

    # Bulk create disciplines for all years
    dyscypliny_zrodel = []
    for discipline in cv.get("disciplines", []):
        nazwa = discipline.get("name")
        dyscyplina = dyscypliny_cache.get(nazwa)
        if not dyscyplina:
            raise DataError(f"Brak dyscypliny o nazwie {nazwa}")

        for rok in range(const.PBN_MIN_ROK, const.PBN_MAX_ROK + 1):
            dyscypliny_zrodel.append(
                Dyscyplina_Zrodla(zrodlo=zrodlo, rok=rok, dyscyplina=dyscyplina)
            )

    if dyscypliny_zrodel:
        Dyscyplina_Zrodla.objects.bulk_create(dyscypliny_zrodel, ignore_conflicts=True)


def importuj_zrodla():
    """Import sources from PBN - re-entrant, can be interrupted and resumed."""
    integruj_zrodla()

    # Cache lookups ONCE (2 queries instead of N + N*M)
    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

    # Filter already imported - supports re-entrancy
    imported_ids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
        "pbn_uid_id", flat=True
    )

    for pbn_journal in pbar(
        query=Journal.objects.filter(status="ACTIVE").exclude(
            pk__in=Subquery(imported_ids)
        ),
        label="Dopisywanie źródeł MNISW...",
    ):
        dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache)
