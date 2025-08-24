"""Simple test for BibTeX export functionality in admin."""

from django.test import TestCase
from model_bakery import baker

from bpp.admin.xlsx_export.formats import PrettyXLSX
from bpp.admin.xlsx_export.resources import (
    BibTeXFormat,
    PatentBibTeXResource,
    Praca_DoktorskaBibTeXResource,
    Praca_HabilitacyjnaBibTeXResource,
    Wydawnictwo_CiagleBibTeXResource,
)
from bpp.models import Patent, Praca_Doktorska, Praca_Habilitacyjna, Wydawnictwo_Ciagle


class TestBibTeXExportInAdmin(TestCase):
    """Test BibTeX export functionality."""

    def test_bibtex_resource_export(self):
        """Test that BibTeX resource can export publications."""
        # Create a simple publication
        wydawnictwo = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny="Test Article",
            rok=2023,
        )

        # Create resource and test export
        resource = Wydawnictwo_CiagleBibTeXResource()
        queryset = Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo.pk)

        result = resource.export(queryset)

        # Check that we get a result
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertIn("Test Article", result_str)

    def test_bibtex_format_properties(self):
        """Test BibTeX format properties."""
        bibtex_format = BibTeXFormat()

        self.assertEqual(bibtex_format.get_title(), "BibTeX")
        self.assertEqual(bibtex_format.get_extension(), "bib")
        self.assertTrue(bibtex_format.can_export())
        self.assertFalse(bibtex_format.can_import())

    def test_format_titles(self):
        """Test that format titles are user-friendly."""
        bibtex_format = BibTeXFormat()
        xlsx_format = PrettyXLSX()

        self.assertEqual(bibtex_format.get_title(), "BibTeX")
        self.assertEqual(xlsx_format.get_title(), "prettyxlsx")

    def test_patent_bibtex_resource_export(self):
        """Test that Patent BibTeX resource can export patents."""
        # Create a simple patent
        patent = baker.make(
            Patent,
            tytul_oryginalny="Test Patent",
            rok=2023,
        )

        # Create resource and test export
        resource = PatentBibTeXResource()
        queryset = Patent.objects.filter(pk=patent.pk)

        result = resource.export(queryset)

        # Check that we get a result
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertIn("Test Patent", result_str)

    def test_praca_doktorska_bibtex_resource_export(self):
        """Test that Praca_Doktorska BibTeX resource can export dissertations."""
        # Create a simple doctoral dissertation
        praca_doktorska = baker.make(
            Praca_Doktorska,
            tytul_oryginalny="Test Doctoral Dissertation",
            rok=2023,
        )

        # Create resource and test export
        resource = Praca_DoktorskaBibTeXResource()
        queryset = Praca_Doktorska.objects.filter(pk=praca_doktorska.pk)

        result = resource.export(queryset)

        # Check that we get a result
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertIn("Test Doctoral Dissertation", result_str)

    def test_praca_habilitacyjna_bibtex_resource_export(self):
        """Test that Praca_Habilitacyjna BibTeX resource can export habilitation theses."""
        # Create a simple habilitation thesis
        praca_habilitacyjna = baker.make(
            Praca_Habilitacyjna,
            tytul_oryginalny="Test Habilitation Thesis",
            rok=2023,
        )

        # Create resource and test export
        resource = Praca_HabilitacyjnaBibTeXResource()
        queryset = Praca_Habilitacyjna.objects.filter(pk=praca_habilitacyjna.pk)

        result = resource.export(queryset)

        # Check that we get a result
        self.assertIsNotNone(result)
        result_str = str(result)
        self.assertIn("Test Habilitation Thesis", result_str)
