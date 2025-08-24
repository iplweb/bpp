"""
Tests for BibTeX export functionality.
"""

from unittest.mock import Mock

import pytest
from model_bakery import baker

from bpp.export.bibtex import (
    export_to_bibtex,
    generate_bibtex_key,
    sanitize_bibtex_string,
    wydawnictwo_ciagle_to_bibtex,
    wydawnictwo_zwarte_to_bibtex,
)
from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Zrodlo


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

    def test_model_to_bibtex_methods(self):
        """Test that model instances have to_bibtex methods."""
        # Create minimal test data
        ciagle = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
        zwarte = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Test Book")

        # Test that methods exist and return strings
        assert hasattr(ciagle, "to_bibtex")
        assert hasattr(zwarte, "to_bibtex")

        ciagle_bibtex = ciagle.to_bibtex()
        zwarte_bibtex = zwarte.to_bibtex()

        assert isinstance(ciagle_bibtex, str)
        assert isinstance(zwarte_bibtex, str)
        assert "Test Article" in ciagle_bibtex
        assert "Test Book" in zwarte_bibtex
