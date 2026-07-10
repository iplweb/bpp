from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


def _wiersz_osoba(osoba, jednostka_nazwa):
    return {
        "osoba_sklejona": osoba,
        "nazwa_jednostki": jednostka_nazwa,
        "wydział": "Wydział Testowy",
        "__xls_loc_sheet__": 0,
        "__xls_loc_row__": 7,
    }


@pytest.mark.django_db
def test_analiza_rozbija_osobe_sklejona_i_matchuje_autora():
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    # Tytul.skrot/nazwa unique + baseline preloaduje „dr/doktor" → get_or_create.
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})

    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"

    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [_wiersz_osoba("dr Jan Kowalski", jednostka.nazwa)]
        )
        analizuj(imp, MockProgress(imp))

    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.dane_znormalizowane["nazwisko"] == "Kowalski"
    assert row.dane_znormalizowane["imię"] == "Jan"
    assert row.dane_znormalizowane["parser_confidence"] == "high"
    assert "parser_alternatywy" in row.dane_znormalizowane


@pytest.mark.django_db
def test_osoba_sklejona_jednym_tokenem_rzuca_parse_error():
    # A3: sklejona komórka rozbita na sam nazwisko (jeden token) → imię puste →
    # AutorForm invalid → XLSParseError. To NIE jest status „brak" (założenie A3).
    from import_common.exceptions import XLSParseError

    baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. Test.")
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter(
            [_wiersz_osoba("Kowalski", "Katedra Testowa")]
        )
        with pytest.raises(XLSParseError):
            analizuj(imp, MockProgress(imp))
