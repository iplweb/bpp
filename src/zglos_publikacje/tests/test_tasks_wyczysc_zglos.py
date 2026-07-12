"""Testy celery-taska retencji plików tmp + rejestracji w CELERYBEAT_SCHEDULE."""

import os
import time

from django.conf import settings
from django.test import override_settings

from zglos_publikacje.storage import zglos_tmp_dir
from zglos_publikacje.tasks import wyczysc_zglos_tmp_pliki

GODZINA = 3600
NAZWA_TASKA = "zglos_publikacje.tasks.wyczysc_zglos_tmp_pliki"


def _ustaw_mtime(sciezka, przed_iloma_godzinami):
    t = time.time() - przed_iloma_godzinami * GODZINA
    os.utime(sciezka, (t, t))


def test_task_kasuje_stare_zostawia_swieze(tmp_path):
    """Task (rdzeń wspólny z komendą) kasuje sieroty >24h, świeże zostawia."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        tmp = zglos_tmp_dir()
        os.makedirs(tmp)
        stary = os.path.join(tmp, "stary.pdf")
        swiezy = os.path.join(tmp, "swiezy.pdf")
        for p, mtime_h in ((stary, 25), (swiezy, 1)):
            with open(p, "wb") as f:
                f.write(b"x" * 10)
            _ustaw_mtime(p, mtime_h)

        wynik = wyczysc_zglos_tmp_pliki()

        assert wynik["skasowane"] == 1
        assert not os.path.exists(stary)
        assert os.path.exists(swiezy)


def test_task_nieistniejacy_katalog_bez_wyjatku(tmp_path):
    """Świeża instalacja (brak katalogu tmp) → task nie rzuca, sygnalizuje brak."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        assert not os.path.exists(zglos_tmp_dir())
        wynik = wyczysc_zglos_tmp_pliki()
        assert wynik["katalog_nieobecny"] is True
        assert wynik["skasowane"] == 0


def test_task_zarejestrowany_w_celerybeat():
    """Task retencji jest wpięty w harmonogram beat (obok rodzeństwa cleanup-*)."""
    nazwy = {wpis["task"] for wpis in settings.CELERYBEAT_SCHEDULE.values()}
    assert NAZWA_TASKA in nazwy
