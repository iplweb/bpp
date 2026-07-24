"""Disciplines synchronization mixin for PBN API client.

Pobranie słownika z PBN korzysta z ``django_pbn_client.sync_dictionary``
(materialize-before-atomic): remote-fetch wykonuje się PRZED transakcją, a
upsert do lokalnych modeli — w świeżym bloku atomic. Wcześniej
``@transaction.atomic`` obejmował cały remote-call.
"""

from django.db import transaction
from django_pbn_client import sync_dictionary

from import_common.core import (
    matchuj_aktualna_dyscypline_pbn,
    matchuj_nieaktualna_dyscypline_pbn,
)
from import_common.normalization import normalize_kod_dyscypliny
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup


class DisciplinesMixin:
    """Mixin providing discipline synchronization methods."""

    def download_disciplines(self):
        """Pobierz słownik dyscyplin z API PBN i zapisz do lokalnej bazy.

        Remote-fetch (``get_disciplines``) wykonuje się poza transakcją; sam
        zapis leci atomowo (patrz ``sync_dictionary``).
        """
        sync_dictionary(self.get_disciplines, self._upsert_disciplines)

    def _upsert_disciplines(self, elems):
        """Upsert pobranego słownika do ``DisciplineGroup``/``Discipline``.

        Wołane WEWNĄTRZ transakcji otwartej przez ``sync_dictionary`` — bez
        własnego ``@transaction.atomic``.
        """
        for elem in elems:
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

    def sync_disciplines(self):
        """Pobierz słownik i zsynchronizuj tłumaczenia dyscyplin BPP.

        Remote-fetch (``download_disciplines``) jest transakcyjnie bezpieczny;
        dopasowanie do modeli BPP leci w OSOBNEJ transakcji
        (``_sync_discipline_translations``). Remote-call NIE jest już
        obejmowany transakcją (wcześniejszy ``@transaction.atomic`` na całej
        metodzie trzymał ją otwartą przez czas pobierania z PBN).
        """
        self.download_disciplines()
        self._sync_discipline_translations()

    @transaction.atomic
    def _sync_discipline_translations(self):
        """Dopasuj aktualny słownik PBN do modeli BPP.

        Matching (``Dyscyplina_Naukowa``/``TlumaczDyscyplin``) jest BPP-specific
        i celowo pozostaje w BPP (nie w pakiecie).
        """
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
            # Każda dyscyplina z aktualnego słownika powinna być wpisana do BPP
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
