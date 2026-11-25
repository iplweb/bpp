"""Druga runda poprawek po przeglądzie obsługi plików z hasłem."""

import json
import logging
import os
import struct
import time
import uuid
from datetime import timedelta
from unittest import mock

import olefile
import pytest
import sentry_sdk
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from liveops.testing import MockProgress

from import_common.exceptions import PlikZabezpieczonyHaslemException
from import_common.util import czy_plik_zaszyfrowany
from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon
from import_polon.tasks import usun_zalegle_pliki_z_haslem
from import_polon.tests.test_plik_z_haslem import (
    HASLO,
    NAGLOWKI_POLON,
    _form_polon,
    _xlsx,
    _zaszyfruj,
)
from import_polon.tests.test_plik_z_haslem_usuwanie import ANALIZA_POLON, _import
from import_polon.utils import (
    PREFIKS_KATALOGU_TYMCZASOWEGO,
    usun_stare_katalogi_tymczasowe,
)


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path


# --------------------------------------------------------------------------
# Syntetyczne kontenery OLE2 (olefile nie umie tworzyć nowych plików, więc
# przerabiamy zaszyfrowany XLSX: zmieniamy nazwy wpisów katalogu i nadpisujemy
# zawartość strumieni tej samej długości).
# --------------------------------------------------------------------------


def _zmien_nazwe_wpisu(dane, stara, nowa):
    """Zmienia nazwę wpisu katalogu OLE2 (128 B: nazwa UTF-16 w 64 B + długość
    w bajtach z terminatorem). Ta sama nazwa bywa też w treści strumieni
    (np. DataSpaceMap), więc szukamy wystąpienia z pasującym polem długości."""
    zakodowana = stara.encode("utf-16-le") + b"\x00\x00"
    poz = dane.find(zakodowana)
    while poz >= 0:
        if struct.unpack_from("<H", dane, poz + 64)[0] == len(zakodowana):
            break
        poz = dane.find(zakodowana, poz + 1)
    assert poz >= 0, stara
    nazwa = nowa.encode("utf-16-le") + b"\x00\x00"
    dane[poz : poz + 64] = nazwa.ljust(64, b"\x00")
    dane[poz + 64 : poz + 66] = struct.pack("<H", len(nazwa))


def _biff(rozmiar, z_filepass=True):
    rekordy = struct.pack("<HH", 0x0809, 16) + b"\x00" * 16  # BOF
    if z_filepass:
        rekordy += struct.pack("<HH", 0x002F, 6) + b"\x01\x00" * 3  # FILEPASS
    rekordy += struct.pack("<HH", 0x000A, 0)  # EOF
    return rekordy.ljust(rozmiar, b"\x00")


def _ole(tmp_path, nazwy, strumienie=None):
    """Zaszyfrowany XLSX z przemianowanymi wpisami katalogu + nadpisanymi
    strumieniami; zwraca ścieżkę."""
    dane = bytearray(_zaszyfruj(_xlsx(NAGLOWKI_POLON)))
    for stara, nowa in nazwy.items():
        _zmien_nazwe_wpisu(dane, stara, nowa)
    p = tmp_path / f"plik-{uuid.uuid4().hex}.xls"
    p.write_bytes(bytes(dane))
    if strumienie:
        ole = olefile.OleFileIO(str(p), write_mode=True)
        for nazwa, budowniczy in strumienie.items():
            ole.write_stream(nazwa, budowniczy(ole.get_size(nazwa)))
        ole.close()
    return p


@pytest.fixture
def xls_duzy_strumien(tmp_path):
    """.xls z FILEPASS w strumieniu Workbook w zwykłych sektorach (>= 4 KB)."""
    return _ole(
        tmp_path,
        {"EncryptedPackage": "Workbook", "EncryptionInfo": "Inny"},
        {"Workbook": _biff},
    )


@pytest.fixture
def xls_maly_strumien(tmp_path):
    """.xls z FILEPASS w małym strumieniu (ministrumień, < 4 KB)."""
    return _ole(
        tmp_path,
        {"EncryptionInfo": "Workbook", "EncryptedPackage": "Inny"},
        {"Workbook": _biff},
    )


def test_syntetyczne_xls_maja_oczekiwany_uklad(xls_duzy_strumien, xls_maly_strumien):
    duzy = olefile.OleFileIO(str(xls_duzy_strumien))
    assert duzy.get_size("Workbook") >= duzy.minisectorcutoff
    maly = olefile.OleFileIO(str(xls_maly_strumien))
    assert maly.get_size("Workbook") < maly.minisectorcutoff


# --------------------------------------------------------------------------
# 1. Kasowanie: najpierw storage, potem pole
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_blad_storage_zostawia_nazwe_a_zadanie_ponawia(admin_user, caplog):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path

    with (
        mock.patch.object(
            FileSystemStorage, "delete", side_effect=PermissionError("brak praw")
        ),
        mock.patch(ANALIZA_POLON, return_value=None),
        caplog.at_level(logging.ERROR),
    ):
        imp.run(MockProgress(imp))

    imp.refresh_from_db()
    assert imp.plik  # nazwa została — da się ponowić
    assert os.path.exists(sciezka)
    assert any(
        "Nie udało się usunąć pliku importu" in r.message for r in caplog.records
    )

    assert usun_zalegle_pliki_z_haslem() == 1
    imp.refresh_from_db()
    assert not imp.plik
    assert not os.path.exists(sciezka)


# --------------------------------------------------------------------------
# 2. Zadanie nie zabiera pliku importowi czekającemu w kolejce
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_zadanie_nie_rusza_niezakonczonego_mlodszego_niz_doba(admin_user):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=True)
    ImportPlikuPolon.objects.filter(pk=imp.pk).update(
        created_on=timezone.now() - timedelta(hours=23)
    )
    assert usun_zalegle_pliki_z_haslem() == 0
    assert os.path.exists(imp.plik.path)


# --------------------------------------------------------------------------
# 3. Hasło nie trafia do zdarzenia Sentry/GlitchTip
# --------------------------------------------------------------------------


class _Transport(sentry_sdk.transport.Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.zdarzenia = []

    def capture_envelope(self, envelope):
        zdarzenie = envelope.get_event()
        if zdarzenie is not None:
            self.zdarzenia.append(zdarzenie)


@pytest.fixture
def sentry_jak_na_produkcji():
    """Sentry z opcjami jak w produkcji (scrubber, before_send) i atrapą
    transportu zamiast sieci."""
    from bpp.sentry_config import opcje_sentry

    transport = _Transport()
    opcje = opcje_sentry()
    opcje.update(dsn="https://klucz@glitchtip.invalid/1", transport=transport)
    sentry_sdk.init(**opcje)
    yield transport
    sentry_sdk.get_global_scope().set_client(None)


def _wybuch(*args, **kwargs):
    raise RuntimeError("awaria biblioteki")


@pytest.mark.django_db
def test_haslo_nie_trafia_do_zdarzenia_sentry(sentry_jak_na_produkcji):
    form = _form_polon(_zaszyfruj(_xlsx(NAGLOWKI_POLON)), haslo=HASLO)

    with mock.patch("msoffcrypto.OfficeFile", _wybuch):
        try:
            form.is_valid()
        except RuntimeError as e:
            sentry_sdk.capture_exception(e)
        else:
            pytest.fail("oczekiwano wyjątku")
    sentry_sdk.flush()

    (zdarzenie,) = sentry_jak_na_produkcji.zdarzenia
    tekst = json.dumps(zdarzenie, default=str, ensure_ascii=False)
    # Ramki z argumentami dekoratorów zostały zserializowane (test ma sens)…
    assert "func_args" in tekst
    assert "przygotuj_plik_importu" in tekst
    # …a hasła nie ma nigdzie.
    assert HASLO not in tekst


def test_haslo_do_pliku_nie_ujawnia_wartosci():
    from import_common.util import HasloDoPliku

    h = HasloDoPliku(HASLO)
    assert HASLO not in repr(h)
    assert HASLO not in str(h)
    assert HASLO not in repr((h,))
    assert h.odslon() == HASLO
    assert h and not HasloDoPliku("")


# --------------------------------------------------------------------------
# 4. Niekompletny kontener szyfrowania
# --------------------------------------------------------------------------


@pytest.fixture
def bez_encrypted_package(tmp_path):
    return _ole(tmp_path, {"EncryptedPackage": "Inny"})


@pytest.fixture
def bez_encrypted_package_zly_xml(tmp_path):
    return _ole(
        tmp_path,
        {"EncryptedPackage": "Inny"},
        {"EncryptionInfo": lambda n: (b"\x04\x00\x04\x00\x40\x00\x00\x00<a").ljust(n)},
    )


@pytest.mark.parametrize(
    "plik", ["bez_encrypted_package", "bez_encrypted_package_zly_xml"]
)
def test_detektor_niekompletny_kontener(plik, request):
    sciezka = request.getfixturevalue(plik)
    with pytest.raises(PlikZabezpieczonyHaslemException, match="uszkodzony"):
        czy_plik_zaszyfrowany(sciezka)


@pytest.mark.django_db
@pytest.mark.parametrize("haslo", [None, HASLO])
@pytest.mark.parametrize(
    "plik", ["bez_encrypted_package", "bez_encrypted_package_zly_xml"]
)
def test_formularz_niekompletny_kontener(plik, haslo, request):
    dane = request.getfixturevalue(plik).read_bytes()
    form = _form_polon(dane, haslo=haslo)
    assert not form.is_valid()
    assert "uszkodzony" in form.errors["plik"][0]


# --------------------------------------------------------------------------
# 5. .xls: rozpoznanie szyfrowania bez wczytywania strumienia Workbook
# --------------------------------------------------------------------------


@pytest.mark.parametrize("plik", ["xls_duzy_strumien", "xls_maly_strumien"])
def test_xls_filepass_rozpoznany_bez_msoffcrypto(plik, request):
    """Xls97File (i ``openstream`` dużego strumienia) wczytuje cały Workbook
    do pamięci jeszcze przed limitami — detektor czyta tylko 1. sektor."""
    sciezka = request.getfixturevalue(plik)
    with (
        mock.patch("msoffcrypto.OfficeFile", side_effect=AssertionError),
        mock.patch(
            "msoffcrypto.format.xls97.Xls97File.__init__", side_effect=AssertionError
        ),
    ):
        if plik == "xls_duzy_strumien":
            with mock.patch.object(
                olefile.OleFileIO, "openstream", side_effect=AssertionError
            ):
                assert czy_plik_zaszyfrowany(sciezka) is True
        else:
            assert czy_plik_zaszyfrowany(sciezka) is True


def test_xls_bez_filepass(tmp_path):
    sciezka = _ole(
        tmp_path,
        {"EncryptedPackage": "Workbook", "EncryptionInfo": "Inny"},
        {"Workbook": lambda n: _biff(n, z_filepass=False)},
    )
    assert czy_plik_zaszyfrowany(sciezka) is False


@pytest.mark.django_db
def test_ogolny_limit_przed_rozpoznawaniem_szyfrowania():
    dane = _zaszyfruj(_xlsx(NAGLOWKI_POLON))
    with (
        mock.patch("import_common.util.MAX_ROZMIAR_PLIKU", 100),
        mock.patch("import_polon.forms.czy_plik_zaszyfrowany") as detektor,
    ):
        form = _form_polon(dane, haslo=HASLO)
        assert not form.is_valid()
    detektor.assert_not_called()
    assert "przekracza" in form.errors["plik"][0]


# --------------------------------------------------------------------------
# 6. Zadanie: błąd jednego rekordu nie przerywa partii
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("wiek_startu", "usuniete"),
    [
        pytest.param(timedelta(minutes=5), 0, id="swiezy-start"),
        pytest.param(timedelta(hours=30), 1, id="stary-start"),
        pytest.param(None, 1, id="bez-startu"),
    ],
)
def test_zadanie_sprzata_tylko_porzucone_importy(admin_user, wiek_startu, usuniete):
    teraz = timezone.now()
    imp = _import(
        ImportPlikuPolon,
        admin_user,
        zaszyfrowany=True,
        started_on=None if wiek_startu is None else teraz - wiek_startu,
        finished_on=None,
    )
    ImportPlikuPolon.objects.filter(pk=imp.pk).update(
        created_on=teraz - timedelta(hours=30)
    )
    sciezka = imp.plik.path

    assert usun_zalegle_pliki_z_haslem() == usuniete

    imp.refresh_from_db()
    assert bool(imp.plik) == (usuniete == 0)
    assert os.path.exists(sciezka) == (usuniete == 0)


@pytest.mark.django_db
def test_zadanie_kontynuuje_po_bledzie_rekordu(admin_user, caplog):
    teraz = timezone.now()
    a = _import(ImportPlikuPolon, admin_user, True, nazwa="a.xlsx", finished_on=teraz)
    b = _import(
        ImportPlikuAbsencji, admin_user, True, nazwa="b.xlsx", finished_on=teraz
    )
    oryginal = ImportPlikuPolon.usun_plik_jesli_byl_zaszyfrowany

    def zepsuty(self):
        if self.pk == a.pk:
            raise RuntimeError("zepsuty rekord")
        return oryginal(self)

    with (
        mock.patch.object(
            ImportPlikuPolon, "usun_plik_jesli_byl_zaszyfrowany", zepsuty
        ),
        caplog.at_level(logging.ERROR),
    ):
        assert usun_zalegle_pliki_z_haslem() == 1

    assert os.path.exists(a.plik.path)
    assert not os.path.exists(b.plik.path)
    assert any(
        "zepsuty rekord" in (r.exc_text or "") or r.exc_info for r in caplog.records
    )


@pytest.mark.django_db
def test_kasowanie_rekordu_usunietego_w_miedzyczasie(admin_user):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path
    ImportPlikuPolon.objects.filter(pk=imp.pk).delete()  # post_delete nie ruszy:
    # brak on_commit w teście bez django_capture_on_commit_callbacks

    imp.usun_plik_jesli_byl_zaszyfrowany()  # nie rzuca

    assert not os.path.exists(sciezka)


# --------------------------------------------------------------------------
# 7. Osierocone katalogi tymczasowe walidacji
# --------------------------------------------------------------------------


def test_usun_stare_katalogi_tymczasowe(tmp_path):
    stary = tmp_path / f"{PREFIKS_KATALOGU_TYMCZASOWEGO}stary"
    stary.mkdir()
    (stary / "plik.xlsx").write_bytes(b"odszyfrowane")
    dawno = time.time() - 2 * 3600
    os.utime(stary, (dawno, dawno))
    swiezy = tmp_path / f"{PREFIKS_KATALOGU_TYMCZASOWEGO}swiezy"
    swiezy.mkdir()
    obcy = tmp_path / "inny-katalog"
    obcy.mkdir()
    os.utime(obcy, (dawno, dawno))

    assert usun_stare_katalogi_tymczasowe(katalog=str(tmp_path)) == 1

    assert not stary.exists()
    assert swiezy.exists()
    assert obcy.exists()


@pytest.mark.django_db
def test_walidacja_uzywa_katalogu_z_prefiksem_i_sprzata(tmp_path, monkeypatch):
    import tempfile

    from import_polon.forms import przygotuj_plik_importu

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    widziane = []

    def spy(sciezka):
        widziane.append(sciezka)
        return []

    with mock.patch("import_polon.forms.usun_stare_katalogi_tymczasowe") as sprzataj:
        przygotuj_plik_importu(
            SimpleUploadedFile("a.xlsx", _xlsx(NAGLOWKI_POLON)), None, spy
        )

    sprzataj.assert_called_once()
    (sciezka,) = widziane
    katalog = os.path.dirname(sciezka)
    assert os.path.dirname(katalog) == str(tmp_path)
    assert os.path.basename(katalog).startswith(PREFIKS_KATALOGU_TYMCZASOWEGO)
    assert not os.path.exists(katalog)


# --------------------------------------------------------------------------
# 9. Zadanie zarejestrowane w Celery pod nazwą z harmonogramu
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_zadanie_zarejestrowane_w_celery(settings):
    from django_bpp.celery_tasks import app

    app.loader.import_default_modules()
    nazwy = {
        w["task"]
        for w in settings.CELERYBEAT_SCHEDULE.values()
        if w["task"].startswith("import_polon.")
    }
    assert nazwy == {"import_polon.tasks.usun_zalegle_pliki_z_haslem_importu_polon"}
    assert nazwy <= set(app.tasks)
