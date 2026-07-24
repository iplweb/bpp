"""Deduplikacja z migracji ``bpp/0471_deduplikuj_autor_jednostka_bez_daty``.

Testujemy funkcje ``deduplikuj`` bezposrednio na aktualnym rejestrze modeli.
Zeby w ogole dalo sie wyprodukowac duplikaty, trzeba na czas testu zdjac
constraint zakladany przez ``0472`` — dokladnie taki stan ma baza produkcyjna
PRZED migracja.
"""

from importlib import import_module

import pytest
from django.apps import apps
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka
from bpp.models.autor import Autor_Jednostka

migracja = import_module("bpp.migrations.0471_deduplikuj_autor_jednostka_bez_daty")

CONSTRAINT = "bpp_autor_jednostka_bez_daty_unikalne"


@pytest.fixture
def bez_constraintu(db):
    # Bez teardownu: DDL w PostgreSQL jest transakcyjny, a testy z ``db``
    # biegna w transakcji wycofywanej na koncu — indeks wraca sam. Proba
    # recznego CREATE INDEX po DELETE w tej samej transakcji i tak wywalilaby
    # sie na "posiada oczekujace zdarzenia wyzwalaczy" (to samo, co wymusza
    # rozdzielenie dedupu i DDL na migracje 0471 i 0472).
    with connection.cursor() as cur:
        cur.execute(f'DROP INDEX IF EXISTS "{CONSTRAINT}"')
    yield


@pytest.mark.django_db
def test_deduplikuj_zostawia_najnizszy_pk_i_przepina_fk(bez_constraintu):
    from import_pracownikow.models import (
        ImportPracownikow,
        ImportPracownikowOdpiecie,
        ImportPracownikowRow,
    )

    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    zostaje = Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    duplikat = Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    assert duplikat.pk > zostaje.pk

    parent = baker.make(ImportPracownikow)
    wiersz = baker.make(ImportPracownikowRow, parent=parent, autor_jednostka=duplikat)
    odpiecie = baker.make(
        ImportPracownikowOdpiecie,
        parent=parent,
        autor_jednostka=duplikat,
        zaznaczone=True,
        wykonane=False,
    )

    migracja.deduplikuj(apps, None)

    assert list(
        Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).values_list(
            "pk", flat=True
        )
    ) == [zostaje.pk]

    # FK przepiete, a nie skasowane kaskadowo:
    wiersz.refresh_from_db()
    odpiecie.refresh_from_db()
    assert wiersz.autor_jednostka_id == zostaje.pk
    assert odpiecie.autor_jednostka_id == zostaje.pk
    assert odpiecie.zaznaczone is True


@pytest.mark.django_db
def test_deduplikuj_scala_zdublowane_odpiecia_z_tego_samego_importu(bez_constraintu):
    from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie

    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    zostaje = Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    duplikat = Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)

    parent = baker.make(ImportPracownikow)
    baker.make(
        ImportPracownikowOdpiecie,
        parent=parent,
        autor_jednostka=zostaje,
        zaznaczone=False,
        wykonane=False,
    )
    baker.make(
        ImportPracownikowOdpiecie,
        parent=parent,
        autor_jednostka=duplikat,
        zaznaczone=True,
        wykonane=True,
    )

    migracja.deduplikuj(apps, None)

    odpiecia = ImportPracownikowOdpiecie.objects.filter(parent=parent)
    assert odpiecia.count() == 1
    ocalale = odpiecia.get()
    assert ocalale.autor_jednostka_id == zostaje.pk
    # Decyzja operatora (zaznaczone/wykonane) nie ginie przy scalaniu:
    assert ocalale.zaznaczone is True
    assert ocalale.wykonane is True


@pytest.mark.django_db
def test_deduplikuj_nie_rusza_datowanych_okresow_zatrudnienia(bez_constraintu):
    from datetime import date

    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)

    pks = [
        Autor_Jednostka.objects.create(
            autor=autor,
            jednostka=jednostka,
            rozpoczal_prace=date(2010, 1, 1),
            zakonczyl_prace=date(2012, 12, 31),
        ).pk,
        Autor_Jednostka.objects.create(
            autor=autor, jednostka=jednostka, rozpoczal_prace=date(2015, 1, 1)
        ).pk,
        Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka).pk,
    ]

    migracja.deduplikuj(apps, None)

    assert set(
        Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).values_list(
            "pk", flat=True
        )
    ) == set(pks)
