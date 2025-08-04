"""
Simplified tests for BibTeX export functionality.
"""
from unittest.mock import Mock

from django.test import TestCase

from bpp.bibtex_export import (
    export_to_bibtex,
    generate_bibtex_key,
    sanitize_bibtex_string,
    wydawnictwo_ciagle_to_bibtex,
    wydawnictwo_zwarte_to_bibtex,
)


class BibTeXExportSimpleTestCase(TestCase):
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

    def test_generate_bibtex_key_basic(self):
        """Test basic BibTeX key generation with minimal mock."""
        wydawnictwo = Mock()
        wydawnictwo.rok = 2023
        wydawnictwo.pk = 123
        wydawnictwo.autorzy_dla_opisu.return_value.first.return_value = None

        key = generate_bibtex_key(wydawnictwo)
        self.assertIn("2023", key)
        self.assertIn("id123", key)

    def test_wydawnictwo_ciagle_minimal_bibtex(self):
        """Test minimal BibTeX export for Wydawnictwo_Ciagle."""
        # Mock wydawnictwo with minimal required fields
        wydawnictwo = Mock()
        wydawnictwo.tytul_oryginalny = "Test Article"
        wydawnictwo.rok = 2023
        wydawnictwo.pk = 1
        wydawnictwo.zrodlo = None  # No journal
        wydawnictwo.doi = None
        wydawnictwo.issn = None
        wydawnictwo.www = None
        mock_queryset = Mock()
        mock_queryset.first.return_value = None
        mock_queryset.__iter__ = Mock(return_value=iter([]))
        wydawnictwo.autorzy_dla_opisu.return_value = mock_queryset
        wydawnictwo.opis_bibliograficzny_autorzy_cache = None
        wydawnictwo.numer_tomu.return_value = None
        wydawnictwo.numer_wydania.return_value = None
        wydawnictwo.zakres_stron.return_value = None

        bibtex = wydawnictwo_ciagle_to_bibtex(wydawnictwo)

        # Check basic structure
        self.assertIn("@article{", bibtex)
        self.assertIn("title = {Test Article}", bibtex)
        self.assertIn("year = {2023}", bibtex)
        self.assertTrue(bibtex.endswith("}\n"))

    def test_wydawnictwo_zwarte_minimal_bibtex(self):
        """Test minimal BibTeX export for Wydawnictwo_Zwarte."""
        # Mock wydawnictwo with minimal required fields
        wydawnictwo = Mock()
        wydawnictwo.tytul_oryginalny = "Test Book"
        wydawnictwo.rok = 2022
        wydawnictwo.pk = 2
        wydawnictwo.get_wydawnictwo.return_value = "Test Publisher"
        wydawnictwo.miejsce_i_rok = "New York 2022"
        wydawnictwo.isbn = None
        wydawnictwo.www = None
        wydawnictwo.strony = None
        wydawnictwo.wydawnictwo_nadrzedne = None
        wydawnictwo.oznaczenie_wydania = None
        wydawnictwo.seria_wydawnicza = None
        wydawnictwo.doi = None
        wydawnictwo.charakter_formalny = None
        mock_queryset = Mock()
        mock_queryset.first.return_value = None
        mock_queryset.__iter__ = Mock(return_value=iter([]))
        wydawnictwo.autorzy_dla_opisu.return_value = mock_queryset
        wydawnictwo.opis_bibliograficzny_autorzy_cache = None
        wydawnictwo._meta = Mock()
        wydawnictwo._meta.model_name = "wydawnictwo_zwarte"

        bibtex = wydawnictwo_zwarte_to_bibtex(wydawnictwo)

        # Check basic structure
        self.assertIn("@book{", bibtex)
        self.assertIn("title = {Test Book}", bibtex)
        self.assertIn("publisher = {Test Publisher}", bibtex)
        self.assertIn("year = {2022}", bibtex)
        self.assertIn("address = {New York}", bibtex)
        self.assertTrue(bibtex.endswith("}\n"))

    def test_export_to_bibtex_empty_list(self):
        """Test export with empty publication list."""
        result = export_to_bibtex([])
        self.assertEqual(result, "")

    def test_export_to_bibtex_mixed_publications(self):
        """Test export with mixed publication types."""
        # Mock Wydawnictwo_Ciagle
        ciagle = Mock()
        ciagle._meta = Mock()
        ciagle._meta.model_name = "wydawnictwo_ciagle"
        ciagle.tytul_oryginalny = "Article"
        ciagle.rok = 2023
        ciagle.pk = 1
        ciagle.zrodlo = None
        mock_ciagle_queryset = Mock()
        mock_ciagle_queryset.first.return_value = None
        mock_ciagle_queryset.__iter__ = Mock(return_value=iter([]))
        ciagle.autorzy_dla_opisu.return_value = mock_ciagle_queryset
        ciagle.opis_bibliograficzny_autorzy_cache = None
        ciagle.numer_tomu.return_value = None
        ciagle.numer_wydania.return_value = None
        ciagle.zakres_stron.return_value = None
        ciagle.doi = None
        ciagle.issn = None
        ciagle.www = None

        # Mock Wydawnictwo_Zwarte
        zwarte = Mock()
        zwarte._meta = Mock()
        zwarte._meta.model_name = "wydawnictwo_zwarte"
        zwarte.tytul_oryginalny = "Book"
        zwarte.rok = 2022
        zwarte.pk = 2
        zwarte.get_wydawnictwo.return_value = "Publisher"
        zwarte.miejsce_i_rok = "City 2022"
        mock_zwarte_queryset = Mock()
        mock_zwarte_queryset.first.return_value = None
        mock_zwarte_queryset.__iter__ = Mock(return_value=iter([]))
        zwarte.autorzy_dla_opisu.return_value = mock_zwarte_queryset
        zwarte.opis_bibliograficzny_autorzy_cache = None
        zwarte.wydawnictwo_nadrzedne = None
        zwarte.charakter_formalny = None
        zwarte.isbn = None
        zwarte.www = None
        zwarte.strony = None
        zwarte.oznaczenie_wydania = None
        zwarte.seria_wydawnicza = None
        zwarte.doi = None

        publications = [ciagle, zwarte]
        result = export_to_bibtex(publications)

        # Should contain both entries
        self.assertIn("@article{", result)
        self.assertIn("@book{", result)
        self.assertIn("Article", result)
        self.assertIn("Book", result)
