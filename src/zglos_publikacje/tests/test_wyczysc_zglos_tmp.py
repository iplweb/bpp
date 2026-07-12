"""Testy komendy `wyczysc_zglos_tmp` (sekcja C specyfikacji).

Komenda kasuje porzucone pliki tymczasowe kreatora zgłoszeń wyłącznie
w katalogu tmp (`protected/zglos_publikacje_tmp/`), nigdy w katalogu
trwałych plików (`protected/zglos_publikacje/`). Strażnik ścieżki
weryfikuje basename katalogu przez równość.
"""

import os
import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from zglos_publikacje.storage import zglos_tmp_dir

GODZINA = 3600
COMMAND_MODULE = "zglos_publikacje.management.commands.wyczysc_zglos_tmp"


def _ustaw_mtime(sciezka, przed_iloma_godzinami):
    """Ustaw mtime pliku na `przed_iloma_godzinami` w przeszłość."""
    t = time.time() - przed_iloma_godzinami * GODZINA
    os.utime(sciezka, (t, t))


def _uruchom(*args):
    """Wywołaj komendę, zwróć złapany stdout jako string."""
    out = StringIO()
    call_command("wyczysc_zglos_tmp", *args, stdout=out)
    return out.getvalue()


def test_stary_plik_kasowany_swiezy_zostaje(tmp_path):
    """Test 8: stary tmp-plik skasowany, świeży zostaje."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        stary = os.path.join(tmp, "stary.pdf")
        swiezy = os.path.join(tmp, "swiezy.pdf")
        with open(stary, "wb") as f:
            f.write(b"x" * 100)
        with open(swiezy, "wb") as f:
            f.write(b"y" * 50)
        _ustaw_mtime(stary, 25)  # > 24 h
        _ustaw_mtime(swiezy, 1)  # świeży

        out = _uruchom()

        assert not os.path.exists(stary)
        assert os.path.exists(swiezy)
        assert "skasowano: 1" in out


def test_dry_run_nic_nie_kasuje(tmp_path):
    """Test 8 (dry-run): oba pliki zostają, raport pokazuje 1 do skasowania."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        stary = os.path.join(tmp, "stary.pdf")
        swiezy = os.path.join(tmp, "swiezy.pdf")
        for p, mtime_h in ((stary, 25), (swiezy, 1)):
            with open(p, "wb") as f:
                f.write(b"z" * 10)
            _ustaw_mtime(p, mtime_h)

        out = _uruchom("--dry-run")

        assert os.path.exists(stary)
        assert os.path.exists(swiezy)
        assert "[DRY-RUN]" in out
        assert "do skasowania: 1" in out


def test_older_than_hours_parametr(tmp_path):
    """Próg wieku jest parametryzowalny przez --older-than-hours."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        plik = os.path.join(tmp, "dwie_godziny.pdf")
        with open(plik, "wb") as f:
            f.write(b"a" * 5)
        _ustaw_mtime(plik, 2)  # 2 h wstecz

        # Domyślny próg 24 h → plik za młody, zostaje.
        _uruchom()
        assert os.path.exists(plik)

        # Próg 1 h → plik starszy niż próg, kasowany.
        _uruchom("--older-than-hours", "1")
        assert not os.path.exists(plik)


def test_straznik_odmawia_na_zlym_katalogu(tmp_path, monkeypatch):
    """Test 9 (strażnik): zła nazwa katalogu → CommandError, nic nie tknięte."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        # Katalog o nazwie trwałego katalogu (basename != tmp).
        zly = os.path.join(str(tmp_path), "protected", "zglos_publikacje")
        os.makedirs(zly)
        plik = os.path.join(zly, "realne_zgloszenie.pdf")
        with open(plik, "wb") as f:
            f.write(b"b" * 20)
        _ustaw_mtime(plik, 100)  # bardzo stary — i tak nie wolno go tknąć

        monkeypatch.setattr(f"{COMMAND_MODULE}.zglos_tmp_dir", lambda: zly)

        with pytest.raises(CommandError):
            call_command("wyczysc_zglos_tmp")

        # Plik realnego zgłoszenia przetrwał.
        assert os.path.exists(plik)


def test_katalog_trwaly_nietkniety(tmp_path):
    """Test 9: stary plik w katalogu TRWAŁYM przeżywa (komenda go nie widzi)."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        trwaly_dir = os.path.join(str(tmp_path), "protected", "zglos_publikacje")
        os.makedirs(trwaly_dir)

        # Stary plik w katalogu TMP — powinien zniknąć.
        tmp_stary = os.path.join(tmp, "porzucony.pdf")
        with open(tmp_stary, "wb") as f:
            f.write(b"c" * 30)
        _ustaw_mtime(tmp_stary, 48)

        # Stary plik TRWAŁY — nie wolno go tknąć.
        trwaly_stary = os.path.join(trwaly_dir, "zgloszenie.pdf")
        with open(trwaly_stary, "wb") as f:
            f.write(b"d" * 30)
        _ustaw_mtime(trwaly_stary, 48)

        _uruchom()

        assert not os.path.exists(tmp_stary)
        assert os.path.exists(trwaly_stary)


def test_nieistniejacy_katalog_czysty_return(tmp_path):
    """Nieistniejący katalog tmp → brak wyjątku, czysty return."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        # NIE tworzymy katalogu tmp.
        assert not os.path.exists(zglos_tmp_dir())
        out = _uruchom()
        assert "nie istnieje" in out


def test_symlink_nietkniety(tmp_path):
    """Symlink w tmp wskazujący na plik trwały NIE jest kasowany."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        trwaly_dir = os.path.join(str(tmp_path), "protected", "zglos_publikacje")
        os.makedirs(trwaly_dir)

        cel = os.path.join(trwaly_dir, "realny.pdf")
        with open(cel, "wb") as f:
            f.write(b"e" * 40)
        _ustaw_mtime(cel, 72)

        link = os.path.join(tmp, "sierota.pdf")
        os.symlink(cel, link)
        # lchown/utime na samym linku — stary mtime linku.
        t = time.time() - 72 * GODZINA
        os.utime(link, (t, t), follow_symlinks=False)

        _uruchom()

        # Ani link, ani jego cel nie skasowane (is_symlink guard).
        assert os.path.islink(link)
        assert os.path.exists(cel)
