"""
Characterization tests pinning the EXACT BibTeX byte output for a
representative populated instance of each publication type.

These exist to guarantee that the behavior-preserving refactor of
``bpp.export.bibtex`` keeps output byte-identical.
"""

import pytest
from model_bakery import baker

from bpp.export.bibtex import (
    generate_bibtex_key,
    praca_doktorska_to_bibtex,
    praca_habilitacyjna_to_bibtex,
    wydawnictwo_ciagle_to_bibtex,
    wydawnictwo_zwarte_to_bibtex,
)
from bpp.models import (
    Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Zrodlo,
)


@pytest.mark.django_db
def test_char_wydawnictwo_ciagle_full():
    autor = baker.make(Autor, nazwisko="Smith", imiona="John")
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal")
    wyd = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Article Title",
        rok=2023,
        zrodlo=zrodlo,
        tom="12",
        nr_zeszytu="4",
        strony="10-20",
        doi="10.1000/test",
        issn="1234-5678",
        www="https://example.com",
    )
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        rekord=wyd,
        autor=autor,
        zapisany_jako="Smith, John",
        kolejnosc=1,
    )

    key = generate_bibtex_key(wyd)
    expected = (
        f"@article{{{key},\n"
        "  title = {Test Article Title},\n"
        "  author = {Smith, John},\n"
        "  journal = {Test Journal},\n"
        "  year = {2023},\n"
        "  volume = {12},\n"
        "  number = {4},\n"
        "  pages = {10-20},\n"
        "  doi = {10.1000/test},\n"
        "  issn = {1234-5678},\n"
        "  url = {https://example.com}\n"
        "}\n"
    )
    assert wydawnictwo_ciagle_to_bibtex(wyd) == expected
    assert key == f"Smith_2023_id{wyd.pk}"


@pytest.mark.django_db
def test_char_wydawnictwo_ciagle_minimal_omits_missing():
    """Missing fields must be omitted, key/year still emitted."""
    autor = baker.make(Autor, nazwisko="Brown", imiona="Bob")
    wyd = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Bare Article",
        rok=2020,
        zrodlo=None,
        tom="",
        nr_zeszytu="",
        strony="",
        doi="",
        issn="",
        www="",
        informacje="",
        szczegoly="",
    )
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        rekord=wyd,
        autor=autor,
        zapisany_jako="Brown, Bob",
        kolejnosc=1,
    )

    key = generate_bibtex_key(wyd)
    expected = (
        f"@article{{{key},\n"
        "  title = {Bare Article},\n"
        "  author = {Brown, Bob},\n"
        "  year = {2020}\n"
        "}\n"
    )
    assert wydawnictwo_ciagle_to_bibtex(wyd) == expected


@pytest.mark.django_db
def test_char_wydawnictwo_zwarte_book_full():
    autor = baker.make(Autor, nazwisko="Johnson", imiona="Jane")
    wydawca = baker.make("bpp.Wydawca", nazwa="Test Publisher")
    seria = baker.make("bpp.Seria_Wydawnicza", nazwa="My Series")
    wyd = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Test Book Title",
        rok=2022,
        wydawca=wydawca,
        wydawca_opis="",
        miejsce_i_rok="New York 2022",
        strony="1-300",
        doi="10.2000/book",
        isbn="978-0-123456-78-9",
        www="https://book.example.com",
        oznaczenie_wydania="2nd ed.",
        seria_wydawnicza=seria,
    )
    baker.make(
        "bpp.Wydawnictwo_Zwarte_Autor",
        rekord=wyd,
        autor=autor,
        zapisany_jako="Johnson, Jane",
        kolejnosc=1,
    )

    key = generate_bibtex_key(wyd)
    expected = (
        f"@book{{{key},\n"
        "  title = {Test Book Title},\n"
        "  author = {Johnson, Jane},\n"
        "  publisher = {Test Publisher},\n"
        "  address = {New York},\n"
        "  year = {2022},\n"
        "  pages = {1-300},\n"
        "  doi = {10.2000/book},\n"
        "  isbn = {978-0-123456-78-9},\n"
        "  url = {https://book.example.com},\n"
        "  edition = {2nd ed.},\n"
        "  series = {My Series}\n"
        "}\n"
    )
    assert wydawnictwo_zwarte_to_bibtex(wyd) == expected


@pytest.mark.django_db
def test_char_wydawnictwo_zwarte_chapter_incollection():
    parent = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Parent Book Title", rok=2023
    )
    autor = baker.make(Autor, nazwisko="Brown", imiona="Bob")
    wydawca = baker.make("bpp.Wydawca", nazwa="Chapter Publisher")
    chapter = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Chapter Title",
        rok=2023,
        wydawca=wydawca,
        wydawca_opis="",
        wydawnictwo_nadrzedne=parent,
        miejsce_i_rok="",
        strony="45-60",
        doi="",
        isbn="",
        www="",
        oznaczenie_wydania="",
        seria_wydawnicza=None,
    )
    baker.make(
        "bpp.Wydawnictwo_Zwarte_Autor",
        rekord=chapter,
        autor=autor,
        zapisany_jako="Brown, Bob",
        kolejnosc=1,
    )

    key = generate_bibtex_key(chapter)
    expected = (
        f"@incollection{{{key},\n"
        "  title = {Chapter Title},\n"
        "  author = {Brown, Bob},\n"
        "  publisher = {Chapter Publisher},\n"
        "  year = {2023},\n"
        "  pages = {45-60},\n"
        "  booktitle = {Parent Book Title}\n"
        "}\n"
    )
    assert wydawnictwo_zwarte_to_bibtex(chapter) == expected


@pytest.mark.django_db
def test_char_praca_doktorska_full():
    autor = baker.make(Autor, nazwisko="Smith", imiona="John")
    uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
    wydzial = baker.make(
        "bpp.Jednostka", nazwa="Faculty of Science", uczelnia=uczelnia, parent=None
    )
    jednostka = baker.make(
        "bpp.Jednostka",
        nazwa="Department",
        parent=wydzial,
        uczelnia=uczelnia,
    )
    praca = baker.make(
        Praca_Doktorska,
        tytul_oryginalny="Doctoral Dissertation Title",
        rok=2023,
        autor=autor,
        jednostka=jednostka,
        miejsce_i_rok="Warsaw 2023",
        www="https://thesis.example.com",
    )

    key = generate_bibtex_key(praca)
    expected = (
        f"@phdthesis{{{key},\n"
        "  title = {Doctoral Dissertation Title},\n"
        "  author = {Smith John},\n"
        "  school = {Faculty of Science},\n"
        "  year = {2023},\n"
        "  type = {Rozprawa doktorska},\n"
        "  address = {Warsaw},\n"
        "  url = {https://thesis.example.com}\n"
        "}\n"
    )
    assert praca_doktorska_to_bibtex(praca) == expected


@pytest.mark.django_db
def test_char_praca_habilitacyjna_full():
    autor = baker.make(Autor, nazwisko="Johnson", imiona="Jane")
    uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
    wydzial = baker.make(
        "bpp.Jednostka", nazwa="Faculty of Medicine", uczelnia=uczelnia, parent=None
    )
    jednostka = baker.make(
        "bpp.Jednostka",
        nazwa="Department",
        parent=wydzial,
        uczelnia=uczelnia,
    )
    praca = baker.make(
        Praca_Habilitacyjna,
        tytul_oryginalny="Habilitation Thesis Title",
        rok=2022,
        autor=autor,
        jednostka=jednostka,
        miejsce_i_rok="Cracow 2022",
        www="https://habil.example.com",
    )

    key = generate_bibtex_key(praca)
    expected = (
        f"@misc{{{key},\n"
        "  title = {Habilitation Thesis Title},\n"
        "  author = {Johnson Jane},\n"
        "  year = {2022},\n"
        "  note = {Rozprawa habilitacyjna},\n"
        "  school = {Faculty of Medicine},\n"
        "  address = {Cracow},\n"
        "  url = {https://habil.example.com}\n"
        "}\n"
    )
    assert praca_habilitacyjna_to_bibtex(praca) == expected
