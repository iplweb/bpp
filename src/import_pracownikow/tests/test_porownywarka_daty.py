"""Porównywarka „plik vs baza" dla dat zatrudnienia (data_od/data_do) w podglądzie
importu + ekstraktory stanów, dopełnianie snapshotu, inwalidacja memo (§9 spec).
"""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikowRow


def _row(dane, autor=None, jednostka=None, aj=None):
    return baker.make(
        ImportPracownikowRow,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
    )


@pytest.mark.django_db
def test_data_od_zgodne_gdy_ta_sama():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    row = _row({"data_zatrudnienia": "2020-01-01"}, autor, jednostka, aj)
    pole = row.porownaj_z_baza()["data_od"]
    assert pole["rozne"] is False
    assert pole["nowy_okres"] is False
    assert row.stany_pol()["data_od"] == "zgodne"


@pytest.mark.django_db
def test_data_od_wypelnienie_null_zmienione():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    row = _row({"data_zatrudnienia": "2021-05-05"}, autor, jednostka, aj)
    pole = row.porownaj_z_baza()["data_od"]
    assert pole["rozne"] is True
    assert pole["nowy_okres"] is False
    assert row.stany_pol()["data_od"] == "zmienione"


@pytest.mark.django_db
def test_data_od_nowy_okres_gdy_stary_zamkniety():
    # Stary okres ZAMKNIĘTY → inna data od = nowy okres (flaga + baza referencyjna).
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    row = _row({"data_zatrudnienia": "2022-09-01"}, autor, jednostka, None)
    pole = row.porownaj_z_baza()["data_od"]
    assert pole["nowy_okres"] is True
    assert pole["rozne"] is True
    assert pole["plik"] == "2022-09-01"
    assert pole["baza"] == "2010-01-01"
    assert row.stany_pol()["data_od"] == "zmienione"


@pytest.mark.django_db
def test_data_od_otwarty_okres_rozne_bez_nowego_okresu():
    # Otwarty okres → inna data od pokazuje różnicę, ale NIE „nowy okres"
    # (celujemy w aktywny; decyzja A). Wiersz ma podpięty aktywny AJ.
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aktywny = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )
    row = _row({"data_zatrudnienia": "2022-09-01"}, autor, jednostka, aktywny)
    pole = row.porownaj_z_baza()["data_od"]
    assert pole["nowy_okres"] is False
    assert pole["rozne"] is True
    assert pole["baza"] == "2010-01-01"
    assert row.stany_pol()["data_od"] == "zmienione"


@pytest.mark.django_db
def test_data_od_brak_gdy_pusty_plik():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    row = _row({}, autor, jednostka, aj)
    assert row.stany_pol()["data_od"] == "brak"


@pytest.mark.django_db
def test_data_od_brak_gdy_pusta_jednostka():
    autor = baker.make(Autor)
    row = _row({"data_zatrudnienia": "2020-01-01"}, autor, None, None)
    assert row.stany_pol()["data_od"] == "brak"
    assert row.porownaj_z_baza()["data_od"]["rozne"] is False


@pytest.mark.django_db
def test_data_do_wstawienie_zmienione():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )
    row = _row({"data_końca_zatrudnienia": "2023-06-30"}, autor, jednostka, aj)
    assert row.porownaj_z_baza()["data_do"]["rozne"] is True
    assert row.stany_pol()["data_do"] == "zmienione"


@pytest.mark.django_db
def test_data_do_roznica_pokazana_nie_nadpisana():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2020, 12, 31),
    )
    row = _row({"data_końca_zatrudnienia": "2023-06-30"}, autor, jednostka, aj)
    pole = row.porownaj_z_baza()["data_do"]
    assert pole["rozne"] is True
    assert pole["baza"] == "2020-12-31"
    assert row.stany_pol()["data_do"] == "zmienione"


@pytest.mark.django_db
def test_data_do_zgodne_gdy_ta_sama():
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2023, 6, 30),
    )
    row = _row({"data_końca_zatrudnienia": "2023-06-30"}, autor, jednostka, aj)
    assert row.porownaj_z_baza()["data_do"]["rozne"] is False
    assert row.stany_pol()["data_do"] == "zgodne"


@pytest.mark.django_db
def test_plik_od_zwraca_date_nie_str():
    # N5: kontrakt — _plik_od parsuje ISO-string do date (resolver wymaga date).
    row = _row({"data_zatrudnienia": "2020-01-01"})
    assert row._plik_od() == date(2020, 1, 1)


@pytest.mark.django_db
def test_snapshot_bez_nowych_kluczy_dopelniony_brak():
    """Stary snapshot (sprzed data_od/data_do) → dopełniony „brak", rekord nie
    znika pod filtrem nowego pola."""
    row = baker.make(
        ImportPracownikowRow,
        autor=None,
        dane_znormalizowane={},
        stany_pol_snapshot={"jednostka": "zgodne"},
    )
    stany = row.stany_pol()
    assert stany["data_od"] == "brak"
    assert stany["data_do"] == "brak"
    assert stany["jednostka"] == "zgodne"


@pytest.mark.django_db
def test_memo_okres_inwalidowane_po_zmianie_autora():
    """N3: zmiana autora + ``_zapomnij_okres`` → kolejny odczyt liczy decyzję dla
    NOWEGO autora (nie stara memo)."""
    a1, a2 = baker.make(Autor), baker.make(Autor)
    jednostka = baker.make(Jednostka)
    baker.make(
        Autor_Jednostka, autor=a1, jednostka=jednostka, rozpoczal_prace=date(2020, 1, 1)
    )
    row = _row({"data_zatrudnienia": "2020-01-01"}, a1, jednostka, None)
    assert row._okres()[0] == "istniejacy"
    row.autor = a2
    row._zapomnij_okres()
    assert row._okres() == ("nowy", date(2020, 1, 1))
