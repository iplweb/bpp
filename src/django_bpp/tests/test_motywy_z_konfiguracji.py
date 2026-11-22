import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from django_bpp.motywy_z_konfiguracji import KATALOG_MOTYWOW, wczytaj_motywy


def _zapisz(katalog, nazwa_pliku, konfig):
    (katalog / nazwa_pliku).write_text(json.dumps(konfig), encoding="utf-8")


def test_wczytaj_motywy_wartosc_i_etykieta(tmp_path):
    _zapisz(tmp_path, "uczelnia-x.json", {"nazwa": "uczelnia-x", "opis": "Granat"})
    _zapisz(tmp_path, "bez-opisu.json", {"nazwa": "bez-opisu"})

    assert wczytaj_motywy(tmp_path) == [
        ("app-bez-opisu", "bez-opisu"),
        ("app-uczelnia-x", "Granat"),
    ]


def test_wczytaj_motywy_pusty_katalog(tmp_path):
    assert wczytaj_motywy(tmp_path) == []


@pytest.mark.parametrize(
    "nazwa_pliku,konfig",
    [
        ("Zla Nazwa.json", {"nazwa": "Zla Nazwa"}),
        ("inna.json", {"nazwa": "uczelnia-x"}),
    ],
)
def test_wczytaj_motywy_odrzuca_zla_nazwe(tmp_path, nazwa_pliku, konfig):
    _zapisz(tmp_path, nazwa_pliku, konfig)
    with pytest.raises(ImproperlyConfigured):
        wczytaj_motywy(tmp_path)


def test_wczytaj_motywy_nie_nadpisuje_recznych_motywow(tmp_path):
    _zapisz(tmp_path, "blue.json", {"nazwa": "blue"})
    with pytest.raises(ImproperlyConfigured, match="zajęta"):
        wczytaj_motywy(tmp_path, zajete=["app-blue"])


def test_katalog_motywow_istnieje():
    assert KATALOG_MOTYWOW.is_dir()
