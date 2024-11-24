from pbn_api.integrator import integruj_zrodla
from pbn_api.models import Journal

from bpp import const
from bpp.models import Dyscyplina_Naukowa, Dyscyplina_Zrodla, Zrodlo
from bpp.util import pbar


def importuj_zrodla():
    integruj_zrodla()

    # Dodaj do tabeli Źródła wszystkie źródła MNISW z PBNu, których tam jeszcze nie ma.

    for pbn_journal in pbar(
        query=Journal.objects.all().exclude(
            pk__in=Zrodlo.objects.values_list("pbn_uid_id", flat=True)
        ),
        label="Dopisywanie źródeł MNISW...",
    ):
        assert pbn_journal.rekord_w_bpp() is None

        cv = pbn_journal.current_version["object"]
        zrodlo = Zrodlo.objects.create(
            nazwa=cv.get("title"),
            skrot=cv.get("title"),
            issn=cv.get("issn"),
            eissn=cv.get("eissn"),
            pbn_uid=pbn_journal,
        )
        for rok, value in cv.get("points").items():
            if value.get("accepted"):
                zrodlo.punktacja_zrodla_set.create(
                    rok=rok, punkty_kbn=value.get("points")
                )

        for discipline in cv.get("disciplines"):
            for rok in range(const.PBN_MIN_ROK, const.PBN_MAX_ROK):
                zrodlo.dyscyplina_zrodla_set.create(
                    rok=rok,
                    dyscyplina=Dyscyplina_Naukowa.objects.get(
                        nazwa=discipline.get("name")
                    ),
                )
                Dyscyplina_Zrodla.objects.create()
