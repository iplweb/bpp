import pytest
from model_bakery import baker

from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
)
from import_pracownikow.pewnosc import STATUS_RECZNY, STATUS_TWARDY, STATUS_WIELU


@pytest.mark.django_db
def test_row_ma_nowe_pola_z_bezpiecznymi_defaultami():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False)
    row.save()
    row.refresh_from_db()
    assert row.confidence is None
    assert row.korekta_uzytkownika == {}
    assert row.wybrany_kandydat is None


@pytest.mark.django_db
def test_confidence_badge_mapuje_status_na_klase_i_ikone():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_TWARDY
    )
    klasa, ikona, etykieta = row.confidence_badge
    assert klasa == "success"
    assert ikona == "fi-check"
    assert "twardy" in etykieta


@pytest.mark.django_db
def test_confidence_badge_reczny_odrozniony_od_twardego():
    """Item 7: ręczny wybór operatora ma WŁASNY badge („wybór użytkownika",
    fi-pencil) — NIE udaje „twardego matcha" (fi-check)."""
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_RECZNY
    )
    klasa, ikona, etykieta = row.confidence_badge
    assert ikona == "fi-pencil"
    assert "użytkownika" in etykieta
    assert "twardy" not in etykieta


@pytest.mark.django_db
def test_confidence_badge_dla_none_ma_bezpieczny_default():
    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(parent=imp, zmiany_potrzebne=False, confidence=None)
    klasa, ikona, etykieta = row.confidence_badge
    assert klasa == "secondary"


@pytest.mark.django_db
def test_kandydat_zapis_i_odczyt_oraz_ordering():
    from bpp.models import Autor

    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU
    )
    row.save()
    a1 = baker.make(Autor, nazwisko="A", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="B", imiona="Jan")
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a1, pewnosc=0.85, powod="polish_english", publikacji_count=3
    )
    ImportPracownikowRowKandydat.objects.create(
        row=row, autor=a2, pewnosc=1.0, powod="iexact", publikacji_count=1
    )
    kandydaci = list(row.kandydaci.all())
    assert len(kandydaci) == 2
    # ordering ["-pewnosc"] — najpewniejszy pierwszy
    assert kandydaci[0].autor_id == a2.pk
    assert kandydaci[0].pewnosc == 1.0


@pytest.mark.django_db
def test_zapisz_dla_nadpisuje_kandydatow_wiersza():
    from dataclasses import dataclass

    from bpp.models import Autor

    @dataclass
    class _K:
        autor: object
        pewnosc: float
        powod: str
        publikacji: int

    imp = baker.make(ImportPracownikow)
    row = ImportPracownikowRow(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU
    )
    row.save()
    a1 = baker.make(Autor, nazwisko="A", imiona="Jan")
    a2 = baker.make(Autor, nazwisko="B", imiona="Jan")

    ImportPracownikowRowKandydat.zapisz_dla(row, [_K(a1, 1.0, "iexact", 2)])
    assert row.kandydaci.count() == 1

    # ponowne wywołanie KASUJE poprzednich i wstawia nowych (mapowanie k.* → pola)
    ImportPracownikowRowKandydat.zapisz_dla(row, [_K(a2, 0.85, "polish_english", 0)])
    kandydaci = list(row.kandydaci.all())
    assert len(kandydaci) == 1
    assert kandydaci[0].autor_id == a2.pk
    assert kandydaci[0].powod == "polish_english"
    assert kandydaci[0].publikacji_count == 0
