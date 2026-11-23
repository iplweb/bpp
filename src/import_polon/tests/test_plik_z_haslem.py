"""Pliki Excel zabezpieczone hasłem w imporcie POLON i absencji.

Zaszyfrowany XLSX to kontener OLE2 (``EncryptionInfo`` + ``EncryptedPackage``),
na którym pandas/xlrd rzuca „Can't find workbook in OLE2 compound document".
Dawniej ten komunikat lądował u użytkownika, a wyjątek w monitoringu błędów.
"""

import io
import logging
from unittest import mock

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from import_polon.forms import NowyImportAbsencjiForm, NowyImportForm

HASLO = "Tajne-Haslo-123!"
XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

NAGLOWKI_POLON = [
    "NAZWISKO",
    "IMIE",
    "ZATRUDNIENIE",
    "OSWIADCZENIE_N",
    "OSWIADCZENIE_O_DYSCYPLINACH",
    "ZATRUDNIENIE_OD",
    "ZATRUDNIENIE_DO",
    "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA",
    "PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA",
    "DYSCYPLINA_N",
    "DYSCYPLINA_N_KOLEJNA",
    "OSWIADCZONA_DYSCYPLINA_PIERWSZA",
    "OSWIADCZONA_DYSCYPLINA_DRUGA",
]

NAGLOWKI_ABSENCJI = ["NAZWISKO", "IMIE", "ROK_NIEOBECNOSC"]


def _xlsx(naglowki):
    df = pd.DataFrame({n: ["x"] for n in naglowki})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _zaszyfruj(dane, haslo=HASLO):
    from msoffcrypto.format.ooxml import OOXMLFile

    wynik = io.BytesIO()
    OOXMLFile(io.BytesIO(dane)).encrypt(haslo, wynik)
    return wynik.getvalue()


def _upload(dane, nazwa="raport.xlsx"):
    return SimpleUploadedFile(nazwa, dane, content_type=XLSX_CT)


def _form_polon(dane, haslo=None):
    data = {"rok": 2023, "zapisz_zmiany_do_bazy": False}
    if haslo is not None:
        data["haslo_do_pliku"] = haslo
    return NowyImportForm(data=data, files={"plik": _upload(dane)})


def _form_absencji(dane, haslo=None):
    data = {"zapisz_zmiany_do_bazy": False}
    if haslo is not None:
        data["haslo_do_pliku"] = haslo
    return NowyImportAbsencjiForm(data=data, files={"plik": _upload(dane)})


@pytest.fixture
def monitoring():
    """Zamockowane wszystkie drogi do monitoringu błędów (GlitchTip/Rollbar)."""
    with (
        mock.patch("import_polon.forms.zaloguj_polkniety_wyjatek") as zaloguj,
        mock.patch("import_polon.utils.capture_exception") as capture_utils,
        mock.patch("bpp.util.wyjatki.capture_exception") as capture_wyjatki,
    ):
        yield [zaloguj, capture_utils, capture_wyjatki]


def _nic_nie_zgloszono(monitoring):
    for m in monitoring:
        assert not m.called, m


@pytest.fixture
def xlsx_polon_zaszyfrowany():
    return _zaszyfruj(_xlsx(NAGLOWKI_POLON))


def test_plik_testowy_naprawde_odtwarza_blad_z_produkcji(xlsx_polon_zaszyfrowany):
    """Bez poprawki pandas pada na tym pliku dokładnie tak jak na produkcji."""
    import xlrd

    with pytest.raises(xlrd.XLRDError, match="Can't find workbook in OLE2"):
        pd.read_excel(io.BytesIO(xlsx_polon_zaszyfrowany))


@pytest.mark.django_db
def test_polon_zaszyfrowany_bez_hasla(xlsx_polon_zaszyfrowany, monitoring):
    form = _form_polon(xlsx_polon_zaszyfrowany)

    assert not form.is_valid()
    blad = form.errors["plik"][0]
    assert "zabezpieczony hasłem" in blad
    assert "Hasło do pliku" in blad
    assert "OLE2" not in blad
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_absencje_zaszyfrowany_bez_hasla(monitoring):
    form = _form_absencji(_zaszyfruj(_xlsx(NAGLOWKI_ABSENCJI)))

    assert not form.is_valid()
    assert "zabezpieczony hasłem" in form.errors["plik"][0]
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_polon_zle_haslo(xlsx_polon_zaszyfrowany, monitoring):
    form = _form_polon(xlsx_polon_zaszyfrowany, haslo="zupelnie-nie-to")

    assert not form.is_valid()
    assert form.errors["plik"] == ["Nieprawidłowe hasło do pliku."]
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_polon_dobre_haslo_podmienia_plik_na_odszyfrowany(
    xlsx_polon_zaszyfrowany, monitoring
):
    form = _form_polon(xlsx_polon_zaszyfrowany, haslo=HASLO)

    assert form.is_valid(), form.errors
    plik = form.cleaned_data["plik"]
    assert plik.name == "raport.xlsx"

    plik.seek(0)
    zawartosc = plik.read()
    # Zwykły XLSX (ZIP), nie kontener OLE2 — i pandas czyta go bez hasła.
    assert zawartosc[:4] == b"PK\x03\x04"
    df = pd.read_excel(io.BytesIO(zawartosc))
    assert list(df.columns) == NAGLOWKI_POLON
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_polon_dobre_haslo_zapisany_plik_czytelny_bez_hasla(
    xlsx_polon_zaszyfrowany, monitoring, admin_user, tmp_path, settings
):
    """Plik zapisany w ``FileField`` (czytany potem przez zadanie w tle
    z dysku) jest już bez hasła."""
    from import_polon.utils import read_excel_or_csv_dataframe_guess_encoding

    settings.MEDIA_ROOT = str(tmp_path)
    form = _form_polon(xlsx_polon_zaszyfrowany, haslo=HASLO)
    assert form.is_valid(), form.errors

    form.instance.owner = admin_user
    obj = form.save()

    df = read_excel_or_csv_dataframe_guess_encoding(obj.plik.path)
    assert list(df.columns) == NAGLOWKI_POLON
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_absencje_dobre_haslo(monitoring):
    form = _form_absencji(_zaszyfruj(_xlsx(NAGLOWKI_ABSENCJI)), haslo=HASLO)

    assert form.is_valid(), form.errors
    plik = form.cleaned_data["plik"]
    plik.seek(0)
    assert plik.read()[:4] == b"PK\x03\x04"


@pytest.mark.django_db
def test_absencje_zle_haslo(monitoring):
    form = _form_absencji(_zaszyfruj(_xlsx(NAGLOWKI_ABSENCJI)), haslo="zle")

    assert not form.is_valid()
    assert form.errors["plik"] == ["Nieprawidłowe hasło do pliku."]
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
def test_polon_dobre_haslo_ale_brak_naglowkow(monitoring):
    """Po odszyfrowaniu plik przechodzi zwykłą walidację nagłówków."""
    form = _form_polon(_zaszyfruj(_xlsx(["NAZWISKO", "IMIE"])), haslo=HASLO)

    assert not form.is_valid()
    assert "nie zawiera wymaganych nagłówków" in form.errors["plik"][0]


@pytest.mark.django_db
def test_niezaszyfrowany_z_haslem_dziala_jak_dotad(monitoring):
    dane = _xlsx(NAGLOWKI_POLON)
    form = _form_polon(dane, haslo="cokolwiek")

    assert form.is_valid(), form.errors
    plik = form.cleaned_data["plik"]
    plik.seek(0)
    assert plik.read() == dane


@pytest.mark.django_db
def test_niezaszyfrowany_bez_hasla_dziala_jak_dotad(monitoring):
    assert _form_polon(_xlsx(NAGLOWKI_POLON)).is_valid()


@pytest.mark.django_db
def test_odszyfrowana_kopia_przechodzi_limity_pliku(
    xlsx_polon_zaszyfrowany, monitoring
):
    """Odszyfrowana zawartość też przechodzi przez ``sprawdz_plik_importu``."""
    with mock.patch("import_common.util.MAX_ROZMIAR_PO_DEKOMPRESJI", 10):
        form = _form_polon(xlsx_polon_zaszyfrowany, haslo=HASLO)
        assert not form.is_valid()

    assert "bomba dekompresyjna" in form.errors["plik"][0]
    _nic_nie_zgloszono(monitoring)


@pytest.mark.django_db
@pytest.mark.parametrize("haslo", [HASLO, "zle-haslo-XYZ", None])
def test_haslo_nie_trafia_do_logow_ani_bledow(
    xlsx_polon_zaszyfrowany, monitoring, caplog, haslo
):
    caplog.set_level(logging.DEBUG)
    form = _form_polon(xlsx_polon_zaszyfrowany, haslo=haslo)
    form.is_valid()

    sprawdzane = [HASLO, "zle-haslo-XYZ"]
    for rekord in caplog.records:
        tekst = rekord.getMessage() + str(rekord.args) + str(rekord.exc_info)
        for h in sprawdzane:
            assert h not in tekst
    for h in sprawdzane:
        assert h not in str(form.errors)
    _nic_nie_zgloszono(monitoring)


def test_pole_hasla_nie_renderuje_wartosci():
    form = NowyImportForm(data={"haslo_do_pliku": HASLO})
    html = str(form["haslo_do_pliku"])
    assert HASLO not in html
    assert 'type="password"' in html
    assert 'autocomplete="new-password"' in html


def test_haslo_na_liscie_pol_zamazywanych(settings):
    from bpp.sentry_config import lista_pol_do_zamazania

    pola = lista_pol_do_zamazania()
    assert "haslo_do_pliku" in pola
    assert "haslo" in pola


@pytest.mark.parametrize("klasa", [NowyImportForm, NowyImportAbsencjiForm])
def test_pole_hasla_jest_w_layoucie_formularza(klasa):
    from crispy_forms.utils import render_crispy_form

    html = render_crispy_form(klasa())
    assert 'name="haslo_do_pliku"' in html
    assert "Hasło do pliku" in html
