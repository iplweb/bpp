"""Guard z migracji ``bpp/0473_guard_autor_jednostka_okresy_bez_nakladan``.

Testujemy funkcje ``sprawdz_nakladania`` bezposrednio. Zeby w ogole dalo sie
wyprodukowac nakladajace sie okresy, trzeba na czas testu zdjac
``ExclusionConstraint`` zakladany przez ``0474`` — dokladnie taki stan ma baza
PRZED migracja.
"""

from datetime import date
from importlib import import_module

import pytest
from django.apps import apps
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka
from bpp.models.autor import Autor_Jednostka

migracja = import_module(
    "bpp.migrations.0473_guard_autor_jednostka_okresy_bez_nakladan"
)

CONSTRAINT = "bpp_autor_jednostka_okresy_bez_nakladan"


class _FakeSchemaEditor:
    """Guard uzywa ``schema_editor.connection.cursor()`` — podajemy realne."""

    def __init__(self, conn):
        self.connection = conn


@pytest.fixture
def bez_constraintu(db):
    # Bez teardownu: DDL w PostgreSQL jest transakcyjny, a testy z ``db`` biegna
    # w transakcji wycofywanej na koncu — constraint wraca sam.
    with connection.cursor() as cur:
        cur.execute(
            f'ALTER TABLE bpp_autor_jednostka DROP CONSTRAINT IF EXISTS "{CONSTRAINT}"'
        )
    yield


@pytest.mark.django_db
def test_guard_przechodzi_gdy_brak_nakladan(bez_constraintu):
    """Rozlaczne i przylegajace okresy -> guard jest no-opem (nie rzuca)."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )
    # przylegajacy (koniec + 1 = start) — NIE nakladanie
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2013, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )

    migracja.sprawdz_nakladania(apps, _FakeSchemaEditor(connection))


@pytest.mark.django_db
def test_guard_odmawia_gdy_okresy_sie_nakladaja(bez_constraintu):
    """Nakladajace sie okresy -> guard ODMAWIA (RuntimeError z lista kolizji)."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2013, 1, 1),
        zakonczyl_prace=date(2018, 12, 31),
    )

    with pytest.raises(RuntimeError) as exc:
        migracja.sprawdz_nakladania(apps, _FakeSchemaEditor(connection))

    assert "NAKLADA" in str(exc.value)


@pytest.mark.django_db
def test_guard_wykrywa_nakladanie_z_otwartym_koncem(bez_constraintu):
    """Otwarty koniec [2010..) nachodzi na pozniejszy okres -> ODMOWA."""
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2015, 1, 1),
        zakonczyl_prace=date(2016, 12, 31),
    )

    with pytest.raises(RuntimeError):
        migracja.sprawdz_nakladania(apps, _FakeSchemaEditor(connection))
