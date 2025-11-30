"""Disciplines synchronization mixin for PBN API client."""

from django.db import transaction

from import_common.core import (
    matchuj_aktualna_dyscypline_pbn,
    matchuj_nieaktualna_dyscypline_pbn,
)
from import_common.normalization import normalize_kod_dyscypliny
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup


class DisciplinesMixin:
    """Mixin providing discipline synchronization methods."""

    @transaction.atomic
    def download_disciplines(self):
        """Zapisuje słownik dyscyplin z API PBN do lokalnej bazy"""

        for elem in self.get_disciplines():
            validityDateFrom = elem.get("validityDateFrom", None)
            validityDateTo = elem.get("validityDateTo", None)
            uuid = elem["uuid"]

            parent_group, created = DisciplineGroup.objects.update_or_create(
                uuid=uuid,
                defaults={
                    "validityDateFrom": validityDateFrom,
                    "validityDateTo": validityDateTo,
                },
            )

            for discipline in elem["disciplines"]:
                Discipline.objects.update_or_create(
                    parent_group=parent_group,
                    uuid=discipline["uuid"],
                    defaults=dict(
                        code=discipline["code"],
                        name=discipline["name"],
                        polonCode=discipline["polonCode"],
                        scientificFieldName=discipline["scientificFieldName"],
                    ),
                )

    @transaction.atomic
    def sync_disciplines(self):
        self.download_disciplines()
        try:
            cur_dg = DisciplineGroup.objects.get_current()
        except DisciplineGroup.DoesNotExist as e:
            raise ValueError(
                "Brak aktualnego słownika dyscyplin na serwerze. Pobierz aktualny "
                "słownik dyscyplin z PBN."
            ) from e

        from bpp.models import Dyscyplina_Naukowa

        for dyscyplina in Dyscyplina_Naukowa.objects.all():
            wpis_tlumacza = TlumaczDyscyplin.objects.get_or_create(
                dyscyplina_w_bpp=dyscyplina
            )[0]

            wpis_tlumacza.pbn_2024_now = matchuj_aktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa
            )
            # Domyślnie szuka dla lat 2018-2022
            wpis_tlumacza.pbn_2017_2021 = matchuj_nieaktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa, rok_min=2018, rok_max=2022
            )

            wpis_tlumacza.pbn_2022_2023 = matchuj_nieaktualna_dyscypline_pbn(
                dyscyplina.kod, dyscyplina.nazwa, rok_min=2023, rok_max=2024
            )

            wpis_tlumacza.save()

        for discipline in cur_dg.discipline_set.all():
            if discipline.name == "weterynaria":
                pass
            # Każda dyscyplina z aktualnego słownika powinna być wpisana do systemu BPP
            try:
                TlumaczDyscyplin.objects.get(pbn_2024_now=discipline)
            except TlumaczDyscyplin.DoesNotExist:
                try:
                    dyscyplina_w_bpp = Dyscyplina_Naukowa.objects.get(
                        kod=normalize_kod_dyscypliny(discipline.code)
                    )
                    TlumaczDyscyplin.objects.get_or_create(
                        dyscyplina_w_bpp=dyscyplina_w_bpp
                    )

                except Dyscyplina_Naukowa.DoesNotExist:
                    dyscyplina_w_bpp = Dyscyplina_Naukowa.objects.create(
                        kod=normalize_kod_dyscypliny(discipline.code),
                        nazwa=discipline.name,
                    )
                    TlumaczDyscyplin.objects.get_or_create(
                        dyscyplina_w_bpp=dyscyplina_w_bpp
                    )
