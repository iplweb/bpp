"""
Tests for BibTeX export functionality.
"""

import datetime
from unittest.mock import Mock

import pytest
from model_bakery import baker

from bpp.export.bibtex import (
    export_to_bibtex,
    generate_bibtex_key,
    patent_to_bibtex,
    praca_doktorska_to_bibtex,
    praca_habilitacyjna_to_bibtex,
    sanitize_bibtex_string,
    wydawnictwo_ciagle_to_bibtex,
    wydawnictwo_zwarte_to_bibtex,
)
from bpp.models import (
    Autor,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Zrodlo,
)


@pytest.mark.django_db
class TestBibTeXExport:
    def test_sanitize_bibtex_string(self):
        """Test that problematic characters are properly escaped."""
        test_cases = [
            ("Test & Title", "Test \\& Title"),
            ("Title with {braces}", "Title with \\{braces\\}"),
            ("Math $formula$", "Math \\$formula\\$"),
            ("Percentage 100%", "Percentage 100\\%"),
            ("Hash #tag", "Hash \\#tag"),
            ("Under_score", "Under\\_score"),
            ("Super^script", "Super\\^script"),
            ("Tilde~space", "Tilde\\~space"),
            (None, ""),
            ("", ""),
        ]

        for input_str, expected in test_cases:
            result = sanitize_bibtex_string(input_str)
            assert (
                result == expected
            ), f"Input: {input_str}, Expected: {expected}, Got: {result}"

    def test_generate_bibtex_key(self):
        """Test BibTeX key generation."""
        # Mock author
        autor = Mock()
        autor.nazwisko = "Kowalski"
        autor.imiona = "Jan"

        # Mock author relation
        autor_rel = Mock()
        autor_rel.autor = autor

        # Mock wydawnictwo
        wydawnictwo = Mock()
        wydawnictwo.rok = 2023
        wydawnictwo.pk = 123
        wydawnictwo.autorzy_dla_opisu.return_value.first.return_value = autor_rel

        key = generate_bibtex_key(wydawnictwo)
        assert "Kowalski" in key
        assert "2023" in key
        assert "id123" in key

    def test_wydawnictwo_ciagle_to_bibtex(self):
        """Test BibTeX export for Wydawnictwo_Ciagle."""
        # Mock zrodlo
        zrodlo = Mock()
        zrodlo.nazwa = "Test Journal"

        # Mock author
        autor = Mock()
        autor.nazwisko = "Smith"
        autor.imiona = "John"

        # Mock author relation
        autor_rel = Mock()
        autor_rel.autor = autor
        autor_rel.zapisany_jako = "Smith, John"

        # Mock wydawnictwo
        wydawnictwo = Mock()
        wydawnictwo.tytul_oryginalny = "Test Article Title"
        wydawnictwo.rok = 2023
        wydawnictwo.zrodlo = zrodlo
        wydawnictwo.doi = "10.1000/test"
        wydawnictwo.issn = "1234-5678"
        wydawnictwo.www = "https://example.com"
        wydawnictwo.pk = 1
        mock_queryset = Mock()
        mock_queryset.first.return_value = autor_rel
        mock_queryset.__iter__ = Mock(return_value=iter([autor_rel]))
        wydawnictwo.autorzy_dla_opisu.return_value = mock_queryset
        wydawnictwo.numer_tomu.return_value = None
        wydawnictwo.numer_wydania.return_value = None
        wydawnictwo.zakres_stron.return_value = "10-20"

        bibtex = wydawnictwo_ciagle_to_bibtex(wydawnictwo)

        # Check that all expected fields are present
        assert "@article{" in bibtex
        assert "title = {Test Article Title}" in bibtex
        assert "author = {Smith, John}" in bibtex
        assert "journal = {Test Journal}" in bibtex
        assert "year = {2023}" in bibtex
        assert "doi = {10.1000/test}" in bibtex
        assert "issn = {1234-5678}" in bibtex
        assert "url = {https://example.com}" in bibtex
        assert "pages = {10-20}" in bibtex
        assert bibtex.endswith("}\n")

    def test_wydawnictwo_zwarte_to_bibtex(self):
        """Test BibTeX export for Wydawnictwo_Zwarte."""
        # Create test data
        autor = baker.make(Autor, nazwisko="Johnson", imiona="Jane")
        wydawca = baker.make("bpp.Wydawca", nazwa="Test Publisher")

        wydawnictwo = baker.make(
            Wydawnictwo_Zwarte,
            tytul_oryginalny="Test Book Title",
            rok=2022,
            wydawca=wydawca,
            miejsce_i_rok="New York 2022",
            isbn="978-0-123456-78-9",
            www="https://book.example.com",
            strony="1-300",
        )

        # Add author
        baker.make(
            "bpp.Wydawnictwo_Zwarte_Autor",
            rekord=wydawnictwo,
            autor=autor,
            zapisany_jako="Johnson, Jane",
            kolejnosc=1,
        )

        bibtex = wydawnictwo_zwarte_to_bibtex(wydawnictwo)

        # Check that all expected fields are present
        assert "@book{" in bibtex
        assert "title = {Test Book Title}" in bibtex
        assert "author = {Johnson, Jane}" in bibtex
        assert "publisher = {Test Publisher}" in bibtex
        assert "year = {2022}" in bibtex
        assert "address = {New York}" in bibtex
        assert "isbn = {978-0-123456-78-9}" in bibtex
        assert "url = {https://book.example.com}" in bibtex
        assert "pages = {1-300}" in bibtex
        assert bibtex.endswith("}\n")

    def test_wydawnictwo_zwarte_chapter_to_bibtex(self):
        """Test BibTeX export for book chapter (Wydawnictwo_Zwarte with parent)."""
        # Create parent book
        parent_book = baker.make(
            Wydawnictwo_Zwarte, tytul_oryginalny="Parent Book Title", rok=2023
        )

        # Create chapter
        autor = baker.make(Autor, nazwisko="Brown", imiona="Bob")
        wydawca = baker.make("bpp.Wydawca", nazwa="Chapter Publisher")

        chapter = baker.make(
            Wydawnictwo_Zwarte,
            tytul_oryginalny="Chapter Title",
            rok=2023,
            wydawca=wydawca,
            wydawnictwo_nadrzedne=parent_book,
            strony="45-60",
        )

        # Add author
        baker.make(
            "bpp.Wydawnictwo_Zwarte_Autor",
            rekord=chapter,
            autor=autor,
            zapisany_jako="Brown, Bob",
            kolejnosc=1,
        )

        bibtex = wydawnictwo_zwarte_to_bibtex(chapter)

        # Check that it's formatted as incollection
        assert "@incollection{" in bibtex
        assert "title = {Chapter Title}" in bibtex
        assert "booktitle = {Parent Book Title}" in bibtex
        assert "author = {Brown, Bob}" in bibtex
        assert "pages = {45-60}" in bibtex

    def test_export_to_bibtex_multiple(self):
        """Test bulk export of multiple publications."""
        # Create test data
        zrodlo = baker.make(Zrodlo, nazwa="Journal")
        autor1 = baker.make(Autor, nazwisko="First", imiona="Author")
        autor2 = baker.make(Autor, nazwisko="Second", imiona="Author")
        wydawca = baker.make("bpp.Wydawca", nazwa="Publisher")

        # Create publications
        ciagle = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny="Article Title",
            rok=2023,
            zrodlo=zrodlo,
        )
        baker.make(
            "bpp.Wydawnictwo_Ciagle_Autor",
            rekord=ciagle,
            autor=autor1,
            zapisany_jako="First, Author",
            kolejnosc=1,
        )

        zwarte = baker.make(
            Wydawnictwo_Zwarte, tytul_oryginalny="Book Title", rok=2023, wydawca=wydawca
        )
        baker.make(
            "bpp.Wydawnictwo_Zwarte_Autor",
            rekord=zwarte,
            autor=autor2,
            zapisany_jako="Second, Author",
            kolejnosc=1,
        )

        publications = [ciagle, zwarte]
        bibtex = export_to_bibtex(publications)

        # Check that both publications are included
        assert "@article{" in bibtex
        assert "@book{" in bibtex
        assert "Article Title" in bibtex
        assert "Book Title" in bibtex
        assert "First, Author" in bibtex
        assert "Second, Author" in bibtex

    def test_patent_to_bibtex(self):
        """Test BibTeX export for Patent."""
        # Create test data
        autor = baker.make(Autor, nazwisko="Tesla", imiona="Nikola")
        wydzial = baker.make("bpp.Wydzial", nazwa="Faculty of Engineering")

        patent = baker.make(
            Patent,
            tytul_oryginalny="Innovative Patent Title",
            rok=2023,
            numer_zgloszenia="P.123456",
            numer_prawa_wylacznego="123456",
            data_zgloszenia=datetime.date(2023, 1, 1),
            data_decyzji=datetime.date(2023, 6, 1),
            www="https://patent.example.com",
            wydzial=wydzial,
        )

        # Add author
        baker.make(
            "bpp.Patent_Autor",
            rekord=patent,
            autor=autor,
            zapisany_jako="Tesla, Nikola",
            kolejnosc=1,
        )

        bibtex = patent_to_bibtex(patent)

        # Check that all expected fields are present
        assert "@misc{" in bibtex
        assert "title = {Innovative Patent Title}" in bibtex
        assert "author = {Tesla, Nikola}" in bibtex
        assert "year = {2023}" in bibtex
        assert "Numer zgłoszenia: P.123456" in bibtex
        assert "Numer prawa wyłącznego: 123456" in bibtex
        assert "url = {https://patent.example.com}" in bibtex
        assert bibtex.endswith("}\n")

    def test_praca_doktorska_to_bibtex(self):
        """Test BibTeX export for Praca_Doktorska."""
        # Create test data
        autor = baker.make(Autor, nazwisko="Smith", imiona="John")
        uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
        wydzial = baker.make(
            "bpp.Wydzial", nazwa="Faculty of Science", uczelnia=uczelnia
        )
        jednostka = baker.make(
            "bpp.Jednostka", nazwa="Department", wydzial=wydzial, uczelnia=uczelnia
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

        bibtex = praca_doktorska_to_bibtex(praca)

        # Check that all expected fields are present
        assert "@phdthesis{" in bibtex
        assert "title = {Doctoral Dissertation Title}" in bibtex
        assert "author = {Smith John}" in bibtex  # Note: format from autorzy_dla_opisu
        assert "school = {Faculty of Science}" in bibtex
        assert "year = {2023}" in bibtex
        assert "type = {Rozprawa doktorska}" in bibtex
        assert "address = {Warsaw}" in bibtex
        assert "url = {https://thesis.example.com}" in bibtex
        assert bibtex.endswith("}\n")

    def test_praca_habilitacyjna_to_bibtex(self):
        """Test BibTeX export for Praca_Habilitacyjna."""
        # Create test data
        autor = baker.make(Autor, nazwisko="Johnson", imiona="Jane")
        uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
        wydzial = baker.make(
            "bpp.Wydzial", nazwa="Faculty of Medicine", uczelnia=uczelnia
        )
        jednostka = baker.make(
            "bpp.Jednostka", nazwa="Department", wydzial=wydzial, uczelnia=uczelnia
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

        bibtex = praca_habilitacyjna_to_bibtex(praca)

        # Check that all expected fields are present
        assert "@misc{" in bibtex
        assert "title = {Habilitation Thesis Title}" in bibtex
        assert (
            "author = {Johnson Jane}" in bibtex
        )  # Note: format from autorzy_dla_opisu
        assert "school = {Faculty of Medicine}" in bibtex
        assert "year = {2022}" in bibtex
        assert "note = {Rozprawa habilitacyjna}" in bibtex
        assert "address = {Cracow}" in bibtex
        assert "url = {https://habil.example.com}" in bibtex
        assert bibtex.endswith("}\n")

    def test_export_to_bibtex_all_types(self):
        """Test bulk export with all publication types."""
        # Create test data
        autor = baker.make(Autor, nazwisko="Multi", imiona="Author")
        zrodlo = baker.make(Zrodlo, nazwa="Journal")
        wydawca = baker.make("bpp.Wydawca", nazwa="Publisher")
        uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
        wydzial = baker.make("bpp.Wydzial", nazwa="Faculty", uczelnia=uczelnia)
        jednostka = baker.make(
            "bpp.Jednostka", nazwa="Department", wydzial=wydzial, uczelnia=uczelnia
        )

        # Create publications of all types
        ciagle = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny="Article Title",
            rok=2023,
            zrodlo=zrodlo,
        )
        baker.make(
            "bpp.Wydawnictwo_Ciagle_Autor",
            rekord=ciagle,
            autor=autor,
            zapisany_jako="Multi, Author",
            kolejnosc=1,
        )

        zwarte = baker.make(
            Wydawnictwo_Zwarte,
            tytul_oryginalny="Book Title",
            rok=2023,
            wydawca=wydawca,
        )
        baker.make(
            "bpp.Wydawnictwo_Zwarte_Autor",
            rekord=zwarte,
            autor=autor,
            zapisany_jako="Multi, Author",
            kolejnosc=1,
        )

        patent = baker.make(
            Patent,
            tytul_oryginalny="Patent Title",
            rok=2023,
        )
        baker.make(
            "bpp.Patent_Autor",
            rekord=patent,
            autor=autor,
            zapisany_jako="Multi, Author",
            kolejnosc=1,
        )

        praca_doktorska = baker.make(
            Praca_Doktorska,
            tytul_oryginalny="PhD Title",
            rok=2023,
            autor=autor,
            jednostka=jednostka,
        )

        praca_habilitacyjna = baker.make(
            Praca_Habilitacyjna,
            tytul_oryginalny="Habil Title",
            rok=2023,
            autor=autor,
            jednostka=jednostka,
        )

        publications = [ciagle, zwarte, patent, praca_doktorska, praca_habilitacyjna]
        bibtex = export_to_bibtex(publications)

        # Check that all publication types are included
        assert "@article{" in bibtex
        assert "@book{" in bibtex
        assert "@misc{" in bibtex
        assert "@phdthesis{" in bibtex
        assert "Article Title" in bibtex
        assert "Book Title" in bibtex
        assert "Patent Title" in bibtex
        assert "PhD Title" in bibtex
        assert "Habil Title" in bibtex

    def test_model_to_bibtex_methods(self):
        """Test that model instances have to_bibtex methods."""
        # Create minimal test data
        autor = baker.make(Autor, nazwisko="Test", imiona="Author")
        uczelnia = baker.make("bpp.Uczelnia", nazwa="University")
        wydzial = baker.make("bpp.Wydzial", nazwa="Faculty", uczelnia=uczelnia)
        jednostka = baker.make(
            "bpp.Jednostka", nazwa="Department", wydzial=wydzial, uczelnia=uczelnia
        )

        ciagle = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
        zwarte = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Test Book")
        patent = baker.make(Patent, tytul_oryginalny="Test Patent")
        praca_doktorska = baker.make(
            Praca_Doktorska,
            tytul_oryginalny="Test PhD",
            autor=autor,
            jednostka=jednostka,
        )
        praca_habilitacyjna = baker.make(
            Praca_Habilitacyjna,
            tytul_oryginalny="Test Habil",
            autor=autor,
            jednostka=jednostka,
        )

        # Test that methods exist and return strings
        models_to_test = [
            (ciagle, "Test Article"),
            (zwarte, "Test Book"),
            (patent, "Test Patent"),
            (praca_doktorska, "Test PhD"),
            (praca_habilitacyjna, "Test Habil"),
        ]

        for model, expected_title in models_to_test:
            assert hasattr(
                model, "to_bibtex"
            ), f"{model._meta.model_name} missing to_bibtex method"
            bibtex = model.to_bibtex()
            assert isinstance(
                bibtex, str
            ), f"{model._meta.model_name} to_bibtex should return string"
            assert (
                expected_title in bibtex
            ), f"{expected_title} not found in bibtex for {model._meta.model_name}"
