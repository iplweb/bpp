"""Testy migracji 0494: ``Autor.opis`` → ``Autor.adnotacje``.

Pole „Opis” (HTML z TinyMCE, pokazywane tylko z flagą ``pokazuj_opis``)
zastąpił biogram. Niepusty opis trafia do wewnętrznych adnotacji (nie do
biogramu — opisy były niepubliczne, biogram by je opublikował), jako zwykły
tekst. Testy działają na czystej funkcji-helperze migracji (bez DB).
"""

import importlib

mod = importlib.import_module("bpp.migrations.0494_autor_opis_do_adnotacji")
polacz = mod.polacz_adnotacje_z_opisem
NAGLOWEK = mod.NAGLOWEK_OPISU


def test_pusty_opis_nie_zmienia_adnotacji():
    assert polacz("Notatka", None) == "Notatka"
    assert polacz("Notatka", "") == "Notatka"
    assert polacz("Notatka", "<p>&nbsp;</p>") == "Notatka"


def test_opis_do_pustych_adnotacji():
    assert polacz("", "Pracownik dydaktyczny") == f"{NAGLOWEK}\nPracownik dydaktyczny"


def test_opis_doklejany_pod_istniejacymi_adnotacjami():
    wynik = polacz("Stara notatka", "Jacek Archiwista")
    assert wynik == f"Stara notatka\n\n{NAGLOWEK}\nJacek Archiwista"


def test_html_zamieniany_na_tekst_z_zachowaniem_akapitow():
    opis = "<p>QGIS, <strong>ArcGIS</strong></p><p>SWD&nbsp;PSP<br>analizy</p>"
    wynik = polacz("", opis)
    assert wynik == f"{NAGLOWEK}\nQGIS, ArcGIS\nSWD PSP\nanalizy"


def test_encje_html_rozwijane():
    assert polacz("", "R&amp;D &lt;test&gt;").endswith("R&D <test>")


def test_idempotencja_nie_dubluje_opisu():
    # Ponowne uruchomienie (np. po częściowym rollbacku) nie dokleja drugi raz.
    raz = polacz("", "Opis autora")
    assert polacz(raz, "Opis autora") == raz
