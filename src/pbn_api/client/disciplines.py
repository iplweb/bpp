"""Disciplines synchronization mixin for PBN API client."""

from django.db import IntegrityError, transaction

from import_common.core import (
    matchuj_aktualna_dyscypline_pbn,
    matchuj_nieaktualna_dyscypline_pbn,
)
from import_common.normalization import normalize_kod_dyscypliny
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup


def _update_or_create_odporne_na_wyscig(manager, defaults, **lookup):
    """``update_or_create`` odporny na równoległy import.

    Właściwej ochrony przed duplikatem dostarcza unikalny constraint na
    (``uuid``) słownika i na (``parent_group``, ``uuid``) dyscypliny — bez
    niego dwa równoległe importy po prostu tworzyły dwa wiersze. Constraint
    sam w sobie zamienia jednak cichy duplikat w ``IntegrityError``, który
    wywala cały import. Tutaj przegrany wyścig jest domykany: wiersz utworzony
    przez równoległy proces zostaje pobrany i zaktualizowany.

    ``transaction.atomic()`` w środku to savepoint — dzięki niemu
    ``IntegrityError`` nie unieważnia transakcji zewnętrznej
    (``download_disciplines`` jest ``@transaction.atomic``) i da się po nim
    dalej odpytywać bazę.
    """
    try:
        with transaction.atomic():
            return manager.update_or_create(defaults=defaults, **lookup)
    except IntegrityError:
        obj = manager.get(**lookup)
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save()
        return obj, False


class DisciplinesMixin:
    """Mixin providing discipline synchronization methods."""

    @transaction.atomic
    def download_disciplines(self):
        """Zapisuje słownik dyscyplin z API PBN do lokalnej bazy"""

        for elem in self.get_disciplines():
            validityDateFrom = elem.get("validityDateFrom", None)
            validityDateTo = elem.get("validityDateTo", None)
            uuid = elem["uuid"]

            parent_group, created = _update_or_create_odporne_na_wyscig(
                DisciplineGroup.objects,
                uuid=uuid,
                defaults={
                    "validityDateFrom": validityDateFrom,
                    "validityDateTo": validityDateTo,
                },
            )

            for discipline in elem["disciplines"]:
                _update_or_create_odporne_na_wyscig(
                    Discipline.objects,
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
