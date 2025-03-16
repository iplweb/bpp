from pathlib import Path

import pytest
from model_bakery import baker

from import_polon.core import (
    analyze_excel_file_import_absencji,
    analyze_excel_file_import_polon,
)
from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon

from bpp.models import Autor, Autor_Dyscyplina


@pytest.fixture
def fn_test_import_polon():
    return Path(__file__).parent / "test_import_polon.xlsx"


@pytest.fixture
def fn_test_import_absencji():
    return Path(__file__).parent / "test_import_absencji.xlsx"


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_zly_plik(fn_test_import_absencji):
    ROK = 2020
    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )
    analyze_excel_file_import_polon(fn_test_import_absencji, ipp)


@pytest.mark.django_db
def test_analyze_excel_file_import_polon(fn_test_import_polon, dyscyplina1):
    ROK = 2020

    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )

    # Artur ZN nie ma żadnego wpisu za ten rok
    artur_dyscyplinazn: Autor = baker.make(
        Autor, imiona="Artur", nazwisko="DyscyplinaZN"
    )

    # Dariusz BezN jest w Nce, ale po imporcie ma go nie być.
    dariusz_dyscyplinabezn: Autor = baker.make(
        Autor, imiona="Dariusz", nazwisko="DyscyplinaBezN"
    )
    dariusz_dyscyplinabezn.autor_dyscyplina_set.create(
        rok=ROK,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
    )

    # Stanisław ZN ma za ten rok wpis, ze nie jest w N
    stanislaw_dyscyplinazn: Autor = baker.make(
        Autor, imiona="Stanisław", nazwisko="DyscyplinaZN"
    )

    stanislaw_dyscyplinazn.autor_dyscyplina_set.create(
        rok=ROK,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.Z,
    )

    analyze_excel_file_import_polon(fn_test_import_polon, ipp)

    assert (
        artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
        == Autor_Dyscyplina.RODZAJE_AUTORA.N
    )
    assert (
        artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).dyscyplina_naukowa
        == dyscyplina1
    )

    assert (
        dariusz_dyscyplinabezn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
        == Autor_Dyscyplina.RODZAJE_AUTORA.Z
    )

    assert (
        stanislaw_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
        == Autor_Dyscyplina.RODZAJE_AUTORA.N
    )


@pytest.mark.django_db
def test_analyze_excel_file_import_absencji(fn_test_import_absencji):
    ipa = baker.make(ImportPlikuAbsencji, zapisz_zmiany_do_bazy=True)

    jan_kowalski: Autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    jan_kowalski.autor_absencja_set.create(rok=2017, ile_dni=50)

    adam_nowak: Autor = baker.make(
        Autor, nazwisko="Nowak", imiona="Adam", orcid="0001-0009-3366-100X"
    )
    adam_nowak_2: Autor = baker.make(Autor, nazwisko="Nowak", imiona="Adam")

    analyze_excel_file_import_absencji(fn_test_import_absencji, ipa)

    assert jan_kowalski.autor_absencja_set.get(rok=2017).ile_dni == 141
    assert jan_kowalski.autor_absencja_set.get(rok=2018).ile_dni == 352

    assert adam_nowak.autor_absencja_set.get(rok=2020).ile_dni == 100
    assert adam_nowak_2.autor_absencja_set.count() == 0


@pytest.mark.django_db
def test_analyze_excel_file_import_absencji_zly_plik(fn_test_import_polon):
    ipa = baker.make(ImportPlikuAbsencji, zapisz_zmiany_do_bazy=True)

    analyze_excel_file_import_absencji(fn_test_import_polon, ipa)
