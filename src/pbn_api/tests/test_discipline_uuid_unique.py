"""Testy unikalności UUID słowników i dyscyplin PBN.

Bug: ``PBNClient.download_disciplines`` robił ``update_or_create`` po polach
bez unikalnego constraintu. Po powstaniu pierwszego duplikatu każdy kolejny
import wywalał się na ``MultipleObjectsReturned`` — na twardo, aż do ręcznego
sprzątnięcia bazy.
"""

import importlib
from pathlib import Path
from uuid import uuid4

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import MultipleObjectsReturned
from django.db import IntegrityError, connection, transaction

from bpp.decorators import json
from bpp.models import Dyscyplina_Naukowa
from pbn_api.const import PBN_GET_DISCIPLINES_URL
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup

MIGRACJA = importlib.import_module("pbn_api.migrations.0076_unikalne_uuid_dyscyplin")


def _zaladuj_fixture_dyscyplin(pbn_client):
    fixture_path = Path(__file__).parent / "fixture_test_get_disciplines.json"
    with open(fixture_path, "rb") as f:
        pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = json.loads(
            f.read()
        )


def _zdejmij_constrainty_unikalnosci():
    """Zdejmuje unikalne constrainty, żeby dało się WYPRODUKOWAĆ duplikaty.

    PostgreSQL wykonuje DDL transakcyjnie, więc rollback testu przywraca
    constrainty — nie zostawiamy po sobie zmienionego schematu.
    """
    with connection.cursor() as cursor:
        for tabela in ("pbn_api_disciplinegroup", "pbn_api_discipline"):
            cursor.execute(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = %s::regclass AND contype = 'u'
                """,
                [tabela],
            )
            for (conname,) in cursor.fetchall():
                cursor.execute(f'ALTER TABLE {tabela} DROP CONSTRAINT "{conname}"')


@pytest.mark.django_db
def test_download_disciplines_dwa_razy_nie_tworzy_duplikatow(pbn_client):
    """Dwukrotny import tego samego słownika nie mnoży wierszy."""
    _zaladuj_fixture_dyscyplin(pbn_client)

    pbn_client.download_disciplines()
    grup_po_pierwszym = DisciplineGroup.objects.count()
    dyscyplin_po_pierwszym = Discipline.objects.count()
    assert dyscyplin_po_pierwszym > 0

    pbn_client.download_disciplines()

    assert DisciplineGroup.objects.count() == grup_po_pierwszym
    assert Discipline.objects.count() == dyscyplin_po_pierwszym


@pytest.mark.django_db
def test_baza_odrzuca_duplikat_uuid_slownika():
    """Constraint na ``DisciplineGroup.uuid`` faktycznie działa w bazie."""
    wspolny_uuid = uuid4()
    DisciplineGroup.objects.create(uuid=wspolny_uuid, validityDateFrom="2024-01-01")

    with pytest.raises(IntegrityError), transaction.atomic():
        DisciplineGroup.objects.create(
            uuid=wspolny_uuid, validityDateFrom="2025-01-01"
        )


@pytest.mark.django_db
def test_baza_odrzuca_duplikat_dyscypliny_w_slowniku():
    """Constraint na parę (słownik, uuid) faktycznie działa w bazie."""
    grupa = DisciplineGroup.objects.create(
        uuid=uuid4(), validityDateFrom="2024-01-01"
    )
    wspolny_uuid = uuid4()
    Discipline.objects.create(
        parent_group=grupa, uuid=wspolny_uuid, code="1.1", name="a"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Discipline.objects.create(
            parent_group=grupa, uuid=wspolny_uuid, code="1.1", name="b"
        )


@pytest.mark.django_db
def test_ten_sam_uuid_dyscypliny_dozwolony_w_roznych_slownikach():
    """UUID dyscypliny NIE jest w PBN unikalny globalnie — tylko w słowniku.

    Regresja na wypadek, gdyby ktoś „naprawił" to constraintem na samym
    ``uuid``: PBN powtarza uuid dyscypliny między kolejnymi słownikami.
    """
    wspolny_uuid = uuid4()
    for rok in (2018, 2022):
        grupa = DisciplineGroup.objects.create(
            uuid=uuid4(), validityDateFrom=f"{rok}-01-01"
        )
        Discipline.objects.create(
            parent_group=grupa, uuid=wspolny_uuid, code="1.1", name="a"
        )

    assert Discipline.objects.filter(uuid=wspolny_uuid).count() == 2


@pytest.mark.django_db
def test_migracja_deduplikuje_slowniki_i_przepina_dyscypliny():
    """Duplikat słownika: zostaje najniższy pk, dyscypliny lecą na niego."""
    _zdejmij_constrainty_unikalnosci()

    wspolny_uuid = uuid4()
    zostaje = DisciplineGroup.objects.create(
        uuid=wspolny_uuid, validityDateFrom="2024-01-01"
    )
    duplikat = DisciplineGroup.objects.create(
        uuid=wspolny_uuid, validityDateFrom="2024-01-01"
    )
    assert duplikat.pk > zostaje.pk

    d_uuid = uuid4()
    Discipline.objects.create(
        parent_group=zostaje, uuid=d_uuid, code="1.1", name="a"
    )
    # ta sama dyscyplina wisząca pod duplikatem słownika — po przepięciu
    # zrobi się z tego kolizja (słownik, uuid), którą krok 2 musi domknąć
    Discipline.objects.create(
        parent_group=duplikat, uuid=d_uuid, code="1.1", name="a"
    )
    # dyscyplina występująca WYŁĄCZNIE pod duplikatem — nie wolno jej zgubić
    inny_uuid = uuid4()
    Discipline.objects.create(
        parent_group=duplikat, uuid=inny_uuid, code="2.2", name="b"
    )

    MIGRACJA.deduplikuj(django_apps, None)

    assert DisciplineGroup.objects.filter(uuid=wspolny_uuid).count() == 1
    assert DisciplineGroup.objects.filter(pk=zostaje.pk).exists()
    assert Discipline.objects.filter(parent_group=zostaje).count() == 2
    assert Discipline.objects.filter(
        parent_group=zostaje, uuid=inny_uuid
    ).exists()


@pytest.mark.django_db
def test_migracja_przepina_fk_tlumacza_dyscyplin():
    """Duplikat dyscypliny: FK z ``TlumaczDyscyplin`` idą na ocalały wiersz."""
    _zdejmij_constrainty_unikalnosci()

    grupa = DisciplineGroup.objects.create(
        uuid=uuid4(), validityDateFrom="2024-01-01"
    )
    d_uuid = uuid4()
    zostaje = Discipline.objects.create(
        parent_group=grupa, uuid=d_uuid, code="1.1", name="a"
    )
    duplikat = Discipline.objects.create(
        parent_group=grupa, uuid=d_uuid, code="1.1", name="a"
    )
    assert duplikat.pk > zostaje.pk

    dyscyplina_bpp = Dyscyplina_Naukowa.objects.create(kod="1.1", nazwa="a")
    tlumacz = TlumaczDyscyplin.objects.create(
        dyscyplina_w_bpp=dyscyplina_bpp,
        pbn_2017_2021=duplikat,
        pbn_2022_2023=duplikat,
        pbn_2024_now=duplikat,
    )

    MIGRACJA.deduplikuj(django_apps, None)

    assert Discipline.objects.filter(uuid=d_uuid).count() == 1
    tlumacz.refresh_from_db()
    assert tlumacz.pbn_2017_2021_id == zostaje.pk
    assert tlumacz.pbn_2022_2023_id == zostaje.pk
    assert tlumacz.pbn_2024_now_id == zostaje.pk


@pytest.mark.django_db
def test_multiple_objects_returned_znika_po_deduplikacji(pbn_client):
    """Pełny scenariusz buga: duplikat → zakleszczony import → naprawa."""
    _zdejmij_constrainty_unikalnosci()

    wspolny_uuid = uuid4()
    for _ in range(2):
        DisciplineGroup.objects.create(
            uuid=wspolny_uuid, validityDateFrom="2024-01-01"
        )

    # PRZED naprawą: import zakleszczony na twardo
    with pytest.raises(MultipleObjectsReturned):
        DisciplineGroup.objects.update_or_create(
            uuid=wspolny_uuid, defaults={"validityDateFrom": "2025-01-01"}
        )

    MIGRACJA.deduplikuj(django_apps, None)

    # PO naprawie: znowu działa
    grupa, created = DisciplineGroup.objects.update_or_create(
        uuid=wspolny_uuid, defaults={"validityDateFrom": "2025-01-01"}
    )
    assert not created
    assert DisciplineGroup.objects.filter(uuid=wspolny_uuid).count() == 1

    # ...a pełny import przechodzi bez wywrotki
    _zaladuj_fixture_dyscyplin(pbn_client)
    pbn_client.download_disciplines()
    assert Discipline.objects.count() > 0


@pytest.mark.django_db
def test_deduplikuj_jest_idempotentne_na_czystej_bazie(pbn_client):
    """Migracja na bazie BEZ duplikatów niczego nie rusza."""
    _zaladuj_fixture_dyscyplin(pbn_client)
    pbn_client.download_disciplines()

    grup = DisciplineGroup.objects.count()
    dyscyplin = Discipline.objects.count()

    MIGRACJA.deduplikuj(django_apps, None)

    assert DisciplineGroup.objects.count() == grup
    assert Discipline.objects.count() == dyscyplin
