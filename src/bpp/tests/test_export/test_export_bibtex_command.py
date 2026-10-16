"""
Testy dla komendy zarządzającej ``export_bibtex``.

Wcześniej istniały wyłącznie testy funkcji z ``bpp.export.bibtex`` (patrz
``test_export_bibtex.py`` / ``test_export_bibtex_simple.py``) — sama komenda
(``handle()``) nie miała żadnego pokrycia. Poniższe testy to smoke test
sprawdzający, że polecenie faktycznie działa end-to-end po refaktorze
rozbijającym ``handle()`` na ``_zbierz_publikacje`` / ``_zapisz_wynik``
(pod C901 z ruff — patrz PR).
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_export_bibtex_do_pliku(tmp_path):
    """``--output`` zapisuje wynik do pliku (ścieżka ``_zapisz_wynik``)."""
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Testowy Artykul", rok=2024)
    output = tmp_path / "out.bib"

    call_command("export_bibtex", "--output", str(output))

    tresc = output.read_text("utf-8")
    assert "@article{" in tresc
    assert "Testowy Artykul" in tresc


@pytest.mark.django_db
def test_export_bibtex_na_stdout(capsys):
    """Bez ``--output`` wynik trafia na stdout (druga gałąź ``_zapisz_wynik``)."""
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Drugi Artykul", rok=2024)

    call_command("export_bibtex")

    out = capsys.readouterr().out
    assert "Drugi Artykul" in out


@pytest.mark.django_db
def test_export_bibtex_filtr_po_roku(capsys):
    """Filtr ``--year`` ogranicza wynik (ścieżka ``_zbierz_publikacje``)."""
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Z Dwudziestego Trzeciego", rok=2023
    )
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Z Dwudziestego Czwartego", rok=2024
    )

    call_command("export_bibtex", "--year", "2024")

    out = capsys.readouterr().out
    assert "Z Dwudziestego Czwartego" in out
    assert "Z Dwudziestego Trzeciego" not in out


@pytest.mark.django_db
def test_export_bibtex_brak_wynikow_rzuca_command_error():
    """Brak trafień po filtrach -> ``CommandError`` (koniec ``_zbierz_publikacje``)."""
    with pytest.raises(CommandError):
        call_command("export_bibtex", "--year", "1900")
