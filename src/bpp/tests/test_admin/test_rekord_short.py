from types import SimpleNamespace

from bpp.admin.wydawnictwo_autor_base import Wydawnictwo_Autor_Base


def _rekord_short(tytul):
    obj = SimpleNamespace(rekord=SimpleNamespace(tytul_oryginalny=tytul))
    return Wydawnictwo_Autor_Base.rekord_short(None, obj)


def test_rekord_short_usuwa_niedozwolone_tagi():
    wynik = _rekord_short("Tytuł <script>alert(1)</script><img src=x onerror=y>")

    assert "<script" not in wynik
    assert "<img" not in wynik
    assert "onerror" not in wynik


def test_rekord_short_zachowuje_dozwolone_formatowanie_i_przycina_html():
    wynik = _rekord_short("H<sub>2</sub>O " + "a" * 200)

    assert wynik.startswith("H<sub>2</sub>O ")
    assert len(wynik) < 200
    assert wynik.endswith("…")


def test_rekord_short_brak_tytulu():
    assert _rekord_short(None) == ""
