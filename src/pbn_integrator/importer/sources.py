"""Journal/source handling for PBN importer."""

from django.db import DataError

from bpp import const
from bpp.models import Dyscyplina_Naukowa, Rodzaj_Zrodla, Zrodlo
from bpp.util import pbar
from pbn_api.models import Journal
from pbn_integrator.utils import integruj_zrodla


def dopisz_jedno_zrodlo(pbn_journal):
    assert pbn_journal.rekord_w_bpp() is None

    cv = pbn_journal.current_version["object"]

    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    zrodlo = Zrodlo.objects.create(
        nazwa=cv.get("title"),
        skrot=cv.get("title"),
        issn=cv.get("issn"),
        e_issn=cv.get("eissn"),
        pbn_uid=pbn_journal,
        rodzaj=rodzaj_periodyk,
    )
    for rok, value in cv.get("points", {}).items():
        if value.get("accepted"):
            zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=value.get("points"))

    for discipline in cv.get("disciplines", []):
        nazwa_dyscypliny = discipline.get("name")
        try:
            dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(nazwa=nazwa_dyscypliny)
        except Dyscyplina_Naukowa.DoesNotExist as err:
            raise DataError(f"Brak dyscypliny o nazwie {nazwa_dyscypliny}") from err

        for rok in range(const.PBN_MIN_ROK, const.PBN_MAX_ROK):
            zrodlo.dyscyplina_zrodla_set.get_or_create(
                rok=rok,
                dyscyplina=dyscyplina_naukowa,
            )


def importuj_zrodla():
    integruj_zrodla()

    # Dodaj do tabeli Źródła wszystkie źródła MNISW z PBNu, których tam jeszcze nie ma.

    # Robimy jako lista bo się popsuje zapytanie
    exclude_list = list(Zrodlo.objects.values_list("pbn_uid_id", flat=True))
    for pbn_journal in pbar(
        query=Journal.objects.filter(status="ACTIVE").exclude(pk__in=exclude_list),
        label="Dopisywanie źródeł MNISW...",
    ):
        dopisz_jedno_zrodlo(pbn_journal)
