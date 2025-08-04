"""
Tests for BibTeX export functionality.
"""
from unittest.mock import Mock

from django.test import TestCase
from model_bakery import baker

from bpp.bibtex_export import (
    export_to_bibtex,
    generate_bibtex_key,
    sanitize_bibtex_string,
    wydawnictwo_ciagle_to_bibtex,
    wydawnictwo_zwarte_to_bibtex,
)
from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Zrodlo


class BibTeXExportTestCase(TestCase):
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
            with self.subTest(input_str=input_str):
                result = sanitize_bibtex_string(input_str)
                self.assertEqual(result, expected)

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
        self.assertIn("Kowalski", key)
        self.assertIn("2023", key)
        self.assertIn("id123", key)

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
        wydawnictwo.autorzy_dla_opisu.return_value = [autor_rel]
        wydawnictwo.autorzy_dla_opisu.return_value.first.return_value = autor_rel
        wydawnictwo.numer_tomu.return_value = None
        wydawnictwo.numer_wydania.return_value = None
        wydawnictwo.zakres_stron.return_value = "10-20"

        bibtex = wydawnictwo_ciagle_to_bibtex(wydawnictwo)

        # Check that all expected fields are present
        self.assertIn("@article{", bibtex)
        self.assertIn("title = {Test Article Title}", bibtex)
        self.assertIn("author = {Smith, John}", bibtex)
        self.assertIn("journal = {Test Journal}", bibtex)
        self.assertIn("year = {2023}", bibtex)
        self.assertIn("doi = {10.1000/test}", bibtex)
        self.assertIn("issn = {1234-5678}", bibtex)
        self.assertIn("url = {https://example.com}", bibtex)
        self.assertIn("pages = {10-20}", bibtex)
        self.assertTrue(bibtex.endswith("}\n"))

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
        self.assertIn("@book{", bibtex)
        self.assertIn("title = {Test Book Title}", bibtex)
        self.assertIn("author = {Johnson, Jane}", bibtex)
        self.assertIn("publisher = {Test Publisher}", bibtex)
        self.assertIn("year = {2022}", bibtex)
        self.assertIn("address = {New York}", bibtex)
        self.assertIn("isbn = {978-0-123456-78-9}", bibtex)
        self.assertIn("url = {https://book.example.com}", bibtex)
        self.assertIn("pages = {1-300}", bibtex)
        self.assertTrue(bibtex.endswith("}\n"))

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
        self.assertIn("@incollection{", bibtex)
        self.assertIn("title = {Chapter Title}", bibtex)
        self.assertIn("booktitle = {Parent Book Title}", bibtex)
        self.assertIn("author = {Brown, Bob}", bibtex)
        self.assertIn("pages = {45-60}", bibtex)

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
        self.assertIn("@article{", bibtex)
        self.assertIn("@book{", bibtex)
        self.assertIn("Article Title", bibtex)
        self.assertIn("Book Title", bibtex)
        self.assertIn("First, Author", bibtex)
        self.assertIn("Second, Author", bibtex)

    def test_model_to_bibtex_methods(self):
        """Test that model instances have to_bibtex methods."""
        # Create minimal test data
        ciagle = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
        zwarte = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Test Book")

        # Test that methods exist and return strings
        self.assertTrue(hasattr(ciagle, "to_bibtex"))
        self.assertTrue(hasattr(zwarte, "to_bibtex"))

        ciagle_bibtex = ciagle.to_bibtex()
        zwarte_bibtex = zwarte.to_bibtex()

        self.assertIsInstance(ciagle_bibtex, str)
        self.assertIsInstance(zwarte_bibtex, str)
        self.assertIn("Test Article", ciagle_bibtex)
        self.assertIn("Test Book", zwarte_bibtex)
