from bpp.util.dbtemplates_disk import disk_template_source


def test_disk_template_source_zwraca_zrodlo_z_dysku():
    # opis_bibliograficzny.html na pewno jest w src/bpp/templates/ (app dir)
    src = disk_template_source("opis_bibliograficzny.html")
    assert src is not None
    # gałąź #329 z dysku (dowód, że to DYSK, nie stary wiersz DB):
    assert "book_title" in src


def test_disk_template_source_none_gdy_brak_pliku():
    assert disk_template_source("nie-ma-takiego-pliku-xyz.html") is None
