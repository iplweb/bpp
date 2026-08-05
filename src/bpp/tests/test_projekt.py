import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from model_bakery import baker

from bpp.models import (
    Finansowanie,
    Grant,
    Instytucja_Finansujaca,
    Projekt,
    Projekt_Autor,
)


@pytest.mark.django_db
def test_projekt_data_zakonczenia_przed_rozpoczeciem(jednostka):
    projekt = Projekt(
        tytul="Testowy",
        jednostka=jednostka,
        data_rozpoczecia="2026-01-01",
        data_zakonczenia="2025-12-31",
    )
    with pytest.raises(ValidationError):
        projekt.clean()


@pytest.mark.django_db
def test_finansowanie_kwota_bez_waluty(jednostka):
    projekt = baker.make(Projekt, jednostka=jednostka)
    instytucja = baker.make(Instytucja_Finansujaca)
    finansowanie = Finansowanie(
        projekt=projekt,
        instytucja=instytucja,
        typ=Finansowanie.TYP_GRANT,
        kwota=1000,
        waluta="",
    )
    with pytest.raises(ValidationError):
        finansowanie.clean()


@pytest.mark.django_db
def test_tylko_jeden_kierownik_projektu(jednostka, autor_jan_nowak, autor_jan_kowalski):
    projekt = baker.make(Projekt, jednostka=jednostka)
    Projekt_Autor.objects.create(
        projekt=projekt, autor=autor_jan_nowak, rola=Projekt_Autor.ROLA_KIEROWNIK
    )
    with pytest.raises(IntegrityError):
        Projekt_Autor.objects.create(
            projekt=projekt,
            autor=autor_jan_kowalski,
            rola=Projekt_Autor.ROLA_KIEROWNIK,
        )


@pytest.mark.django_db
def test_kasowanie_projektu_zostawia_grant(jednostka):
    projekt = baker.make(Projekt, jednostka=jednostka)
    grant = baker.make(Grant, numer_projektu="ABC/123", projekt=projekt)
    projekt.delete()
    grant.refresh_from_db()
    assert grant.pk is not None
    assert grant.projekt is None
