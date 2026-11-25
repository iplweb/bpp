"""Rozpoznawanie i odszyfrowywanie plików Office zabezpieczonych hasłem
we wspólnym bezpieczniku plików importu (``sprawdz_plik_importu``)."""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from import_common.exceptions import (
    NiebezpiecznyPlikException,
    NieprawidloweHasloDoPlikuException,
    PlikZabezpieczonyHaslemException,
)
from import_common.sources import otworz_zrodlo
from import_common.util import (
    KOMUNIKAT_PLIK_Z_HASLEM,
    XLSImportFile,
    czy_plik_zaszyfrowany,
    odszyfruj_plik,
    sprawdz_plik_importu,
    znajdz_naglowek,
)

HASLO = "Haslo-Do-Pliku-42"


def _xlsx_bytes():
    wb = openpyxl.Workbook()
    wb.active.append(["nazwisko", "imię", "jednostka"])
    wb.active.append(["Kowalski", "Jan", "Katedra"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _zaszyfrowany_bytes():
    from msoffcrypto.format.ooxml import OOXMLFile

    wynik = io.BytesIO()
    OOXMLFile(io.BytesIO(_xlsx_bytes())).encrypt(HASLO, wynik)
    return wynik.getvalue()


@pytest.fixture
def zaszyfrowany(tmp_path):
    p = tmp_path / "zaszyfrowany.xlsx"
    p.write_bytes(_zaszyfrowany_bytes())
    return p


def test_wyjatek_ma_wspolna_baze_z_bezpiecznikami():
    # Widoki łapią NiebezpiecznyPlikException i pokazują komunikat — dzięki
    # temu plik z hasłem obsługują bez żadnych zmian.
    assert issubclass(PlikZabezpieczonyHaslemException, NiebezpiecznyPlikException)


def test_czy_plik_zaszyfrowany_sciezka(zaszyfrowany, tmp_path):
    assert czy_plik_zaszyfrowany(zaszyfrowany)
    assert czy_plik_zaszyfrowany(str(zaszyfrowany))

    zwykly = tmp_path / "zwykly.xlsx"
    zwykly.write_bytes(_xlsx_bytes())
    assert not czy_plik_zaszyfrowany(zwykly)

    csv = tmp_path / "plik.csv"
    csv.write_text("NAZWISKO;IMIE\nKowalski;Jan\n")
    assert not czy_plik_zaszyfrowany(csv)

    assert not czy_plik_zaszyfrowany(tmp_path / "nie-ma-takiego.xlsx")


def test_czy_plik_zaszyfrowany_uszkodzony_ole2(tmp_path):
    """Sama sygnatura OLE2 bez sensownej zawartości to nie „plik z hasłem"."""
    p = tmp_path / "smieci.xls"
    p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
    assert not czy_plik_zaszyfrowany(p)


def test_czy_plik_zaszyfrowany_obiekt_plikowy_przywraca_pozycje():
    plik = SimpleUploadedFile("a.xlsx", _zaszyfrowany_bytes())
    plik.seek(5)
    assert czy_plik_zaszyfrowany(plik)
    assert plik.tell() == 5


def test_sprawdz_plik_importu_odrzuca_plik_z_haslem(zaszyfrowany):
    with pytest.raises(PlikZabezpieczonyHaslemException) as exc:
        sprawdz_plik_importu(zaszyfrowany)
    assert str(exc.value) == KOMUNIKAT_PLIK_Z_HASLEM
    assert "Chroń skoroszyt" in str(exc.value)


def test_sprawdz_plik_importu_obiekt_plikowy():
    with pytest.raises(PlikZabezpieczonyHaslemException):
        sprawdz_plik_importu(SimpleUploadedFile("a.xlsx", _zaszyfrowany_bytes()))


def test_znajdz_naglowek_odrzuca_plik_z_haslem(zaszyfrowany):
    with pytest.raises(PlikZabezpieczonyHaslemException):
        znajdz_naglowek(str(zaszyfrowany))


def test_xls_import_file_odrzuca_plik_z_haslem(zaszyfrowany):
    with pytest.raises(PlikZabezpieczonyHaslemException):
        XLSImportFile(str(zaszyfrowany)).xl_workbook  # noqa: B018


def test_otworz_zrodlo_odrzuca_plik_z_haslem(zaszyfrowany):
    """Bez kontroli ``wykryj_format`` brał zaszyfrowany XLSX (OLE2, nie ZIP)
    za CSV i parsował binarne śmieci."""
    with pytest.raises(PlikZabezpieczonyHaslemException):
        otworz_zrodlo(str(zaszyfrowany))


def test_odszyfruj_plik_dobre_haslo(zaszyfrowany, tmp_path):
    dane = odszyfruj_plik(zaszyfrowany, HASLO)
    assert dane[:4] == b"PK\x03\x04"

    p = tmp_path / "odszyfrowany.xlsx"
    p.write_bytes(dane)
    sprawdz_plik_importu(p)  # już bez hasła — przechodzi
    wb = openpyxl.load_workbook(p)
    assert wb.active["A2"].value == "Kowalski"


def test_odszyfruj_plik_zle_haslo_bez_hasla_w_wyjatku(zaszyfrowany):
    with pytest.raises(NieprawidloweHasloDoPlikuException) as exc:
        odszyfruj_plik(zaszyfrowany, "zle-haslo-ABC")
    assert str(exc.value) == "Nieprawidłowe hasło do pliku."
    assert "zle-haslo-ABC" not in repr(exc.value)
    # Bez łańcucha wyjątków msoffcrypto (``from None``).
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__
