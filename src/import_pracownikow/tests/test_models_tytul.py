"""Testy modelu ``ImportPracownikowTytul`` (mirror ``ImportPracownikowJednostka``,
uproszczony — tytuł nie ma drzewa/parenta) i pól tytułowych na
``ImportPracownikowRow``."""

import pytest
from django.db import IntegrityError, transaction
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)


@pytest.mark.django_db
def test_tytul_decyzja_baker_make_dziala():
    imp = baker.make(ImportPracownikow)
    dec = baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="dr hab.",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
    )
    dec.refresh_from_db()
    assert dec.parent_id == imp.pk
    assert dec.nazwa_zrodlowa == "dr hab."
    # domyślna decyzja = akceptuj
    assert dec.decyzja == ImportPracownikowTytul.DECYZJA_AKCEPTUJ
    # pola tekstowe „do utworzenia” domyślnie puste
    assert dec.nazwa_do_utworzenia == ""
    assert dec.skrot_do_utworzenia == ""


@pytest.mark.django_db
def test_tytul_unique_together_parent_nazwa():
    imp = baker.make(ImportPracownikow)
    ImportPracownikowTytul.objects.create(
        parent=imp,
        nazwa_zrodlowa="dr hab.",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ImportPracownikowTytul.objects.create(
                parent=imp,
                nazwa_zrodlowa="dr hab.",
                tryb=ImportPracownikowTytul.TRYB_BRAK,
            )


@pytest.mark.django_db
def test_tytul_unique_together_rozne_parenty_ok():
    imp1 = baker.make(ImportPracownikow)
    imp2 = baker.make(ImportPracownikow)
    ImportPracownikowTytul.objects.create(
        parent=imp1, nazwa_zrodlowa="dr hab.", tryb=ImportPracownikowTytul.TRYB_BRAK
    )
    # Ta sama nazwa, ale inny parent — dozwolone.
    ImportPracownikowTytul.objects.create(
        parent=imp2, nazwa_zrodlowa="dr hab.", tryb=ImportPracownikowTytul.TRYB_BRAK
    )
    assert ImportPracownikowTytul.objects.filter(nazwa_zrodlowa="dr hab.").count() == 2


@pytest.mark.django_db
def test_tytul_related_name_tytuly_do_decyzji():
    imp = baker.make(ImportPracownikow)
    dec = ImportPracownikowTytul.objects.create(
        parent=imp, nazwa_zrodlowa="prof.", tryb=ImportPracownikowTytul.TRYB_BRAK
    )
    assert list(imp.tytuly_do_decyzji.all()) == [dec]


@pytest.mark.django_db
def test_row_related_name_wiersze_tytul():
    imp = baker.make(ImportPracownikow)
    dec = ImportPracownikowTytul.objects.create(
        parent=imp, nazwa_zrodlowa="dr", tryb=ImportPracownikowTytul.TRYB_BRAK
    )
    row = ImportPracownikowRow(parent=imp, zrodlo_tytulu=dec, zmiany_potrzebne=False)
    row.save()
    assert list(dec.wiersze_tytul.all()) == [row]


@pytest.mark.django_db
def test_row_tytul_status_domyslnie_none():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False)
    row.save()
    row.refresh_from_db()
    assert row.tytul_status is None
    assert row.zrodlo_tytulu is None
