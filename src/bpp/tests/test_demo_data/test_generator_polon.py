"""Generator fałszywego pliku POL-on (``bpp.demo_data.generators.polon``)."""

import datetime
from decimal import Decimal

import openpyxl
import pytest
from django.core.management import call_command

from bpp.demo_data.default_dyscypliny import seed_default_dyscypliny
from bpp.demo_data.generators.polon import (
    DOMYSLNE_DYSCYPLINY,
    DYSCYPLINA_SPOZA_SLOWNIKA,
    NAGLOWKI,
    OBCA_UCZELNIA_DOMYSLNA,
    OSOBA_SPOZA_BPP,
    domyslna_nazwa_pliku,
    orcid_z_suma_kontrolna,
    parsuj_dyscypliny,
    write_polon_file,
)
from bpp.models import Autor, Autor_Jednostka

# Wymagane przez formularz/importer (src/import_polon/forms.py).
WYMAGANE = {
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
}


def _czytaj(plik):
    wb = openpyxl.load_workbook(plik)
    assert wb.sheetnames == ["Output"]
    wiersze = list(wb.worksheets[0].iter_rows(values_only=True))
    naglowek, dane = wiersze[0], wiersze[1:]
    return list(naglowek), [dict(zip(naglowek, w, strict=True)) for w in dane]


def test_orcid_suma_kontrolna():
    # Przykład z dokumentacji ORCID.
    assert orcid_z_suma_kontrolna("000000021825009") == "0000-0002-1825-0097"
    assert orcid_z_suma_kontrolna("000000021694233") == "0000-0002-1694-233X"


def test_parsuj_dyscypliny():
    assert parsuj_dyscypliny(None) == list(DOMYSLNE_DYSCYPLINY)
    assert parsuj_dyscypliny(["filozofia=3.5", "archeologia"]) == [
        ("filozofia", Decimal("3.5")),
        ("archeologia", Decimal("15")),
    ]
    assert parsuj_dyscypliny(["nauki teologiczne = 5"]) == [
        ("nauki teologiczne", Decimal("5"))
    ]


def test_domyslna_nazwa_pliku():
    assert domyslna_nazwa_pliku(datetime.date(2026, 1, 15)) == (
        "rozszerzone_zestawienie_pracownikow_podmiotu_na_dzien_"
        "wygenerowania_raportu_2026-01-15.xlsx"
    )


@pytest.fixture
def autorzy_uczelni(jednostka):
    """30 autorów o unikalnych nazwiskach + para imienników (do pominięcia)."""
    autorzy = []
    for i in range(30):
        autorzy.append(Autor.objects.create(imiona=f"Imię{i}", nazwisko=f"Unikalny{i}"))
    for _ in range(2):
        autorzy.append(Autor.objects.create(imiona="Jan", nazwisko="Imiennik"))
    for autor in autorzy:
        Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    return autorzy


@pytest.mark.django_db
def test_write_polon_file_naglowki_i_wartosci(autorzy_uczelni, jednostka, tmp_path):
    seed_default_dyscypliny()
    uczelnia = jednostka.uczelnia
    podsumowanie = write_polon_file(
        tmp_path,
        uczelnia=uczelnia,
        dyscypliny=[("filozofia", Decimal("4")), ("archeologia", Decimal("2"))],
        seed=1,
        dzien=datetime.date(2026, 1, 15),
    )
    assert podsumowanie.plik == tmp_path / domyslna_nazwa_pliku(
        datetime.date(2026, 1, 15)
    )

    naglowek, dane = _czytaj(podsumowanie.plik)
    assert naglowek == list(NAGLOWKI)
    assert len(naglowek) == 43
    assert WYMAGANE <= set(naglowek)
    assert len(dane) == podsumowanie.wierszy

    # Wszystko jako napisy (jak w prawdziwym eksporcie).
    for wiersz in dane:
        for wartosc in wiersz.values():
            assert wartosc is None or isinstance(wartosc, str)
        assert wiersz["OSWIADCZENIE_N"] in ("Tak", "Nie")
        assert wiersz["OSWIADCZENIE_O_DYSCYPLINACH"] in ("Tak", "Nie")

    nasze = [w for w in dane if w["ZATRUDNIENIE"].startswith(uczelnia.nazwa)]
    obce = [w for w in dane if not w["ZATRUDNIENIE"].startswith(uczelnia.nazwa)]
    assert len(obce) == 1
    assert obce[0]["ZATRUDNIENIE"].startswith(OBCA_UCZELNIA_DOMYSLNA)
    for w in nasze:
        assert w["ZATRUDNIENIE"] in (
            f"{uczelnia.nazwa} (Nauczyciel akademicki>Pracownik badawczo-dydaktyczny)",
            f"{uczelnia.nazwa} (Nauczyciel akademicki>Pracownik dydaktyczny)",
        )

    # Imiennicy nie trafiają do pliku (importer nie rozstrzygnąłby remisu).
    assert all(w["NAZWISKO"] != "Imiennik" for w in dane)

    w_n = [w for w in dane if w["OSWIADCZENIE_N"] == "Tak"]
    assert {w["DYSCYPLINA_N"] for w in w_n} >= {"filozofia", "archeologia"}
    dwie = [w for w in w_n if w["DYSCYPLINA_N_KOLEJNA"]]
    assert dwie
    assert {w["PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA"] for w in dwie} == {"60"}

    # Celowo błędne wiersze — po jednym z rodzaju.
    assert len(podsumowanie.bledne_wiersze) == 4
    assert any(w["NAZWISKO"] == OSOBA_SPOZA_BPP[1] for w in dane)
    assert any(w["DYSCYPLINA_N"] == DYSCYPLINA_SPOZA_SLOWNIKA for w in dane)
    assert any(
        w["OSWIADCZENIE_N"] == "Tak"
        and w["WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA"] is None
        for w in dane
    )

    assert podsumowanie.fte_n["filozofia"] >= 4
    assert podsumowanie.fte_n["archeologia"] >= 2
    assert not podsumowanie.ostrzezenia


@pytest.mark.django_db
def test_write_polon_file_deterministyczny_i_bez_blednych(
    autorzy_uczelni, jednostka, tmp_path
):
    seed_default_dyscypliny()
    kw = dict(
        uczelnia=jednostka.uczelnia,
        dyscypliny=[("filozofia", Decimal("3"))],
        seed=7,
        bledne_wiersze=False,
    )
    a = write_polon_file(tmp_path / "a.xlsx", **kw)
    b = write_polon_file(tmp_path / "b.xlsx", **kw)
    assert _czytaj(a.plik) == _czytaj(b.plik)
    assert a.bledne_wiersze == []
    _, dane = _czytaj(a.plik)
    assert all(w["ZATRUDNIENIE"].startswith(jednostka.uczelnia.nazwa) for w in dane)


@pytest.mark.django_db
def test_write_polon_file_ostrzega_gdy_brak_autorow(
    autorzy_uczelni, jednostka, tmp_path
):
    seed_default_dyscypliny()
    podsumowanie = write_polon_file(
        tmp_path / "x.xlsx",
        uczelnia=jednostka.uczelnia,
        dyscypliny=[("filozofia", Decimal("500"))],
        seed=1,
    )
    assert podsumowanie.ostrzezenia
    assert podsumowanie.fte_n["filozofia"] < 500


@pytest.mark.django_db
def test_write_polon_file_nieznana_dyscyplina(jednostka, tmp_path):
    with pytest.raises(ValueError, match="nie-ma-takiej"):
        write_polon_file(
            tmp_path / "x.xlsx",
            uczelnia=jednostka.uczelnia,
            dyscypliny=[("nie-ma-takiej", Decimal("1"))],
        )


@pytest.mark.django_db
def test_command_generuj_plik_polon_demo(autorzy_uczelni, jednostka, tmp_path):
    from io import StringIO

    seed_default_dyscypliny()
    out = StringIO()
    call_command(
        "generuj_plik_polon_demo",
        f"--out={tmp_path / 'p.xlsx'}",
        f"--uczelnia={jednostka.uczelnia.skrot}",
        "--dyscypliny",
        "filozofia=2",
        "--bez-blednych-wierszy",
        "--seed=3",
        stdout=out,
    )
    assert (tmp_path / "p.xlsx").exists()
    assert "Plik POL-on" in out.getvalue()
