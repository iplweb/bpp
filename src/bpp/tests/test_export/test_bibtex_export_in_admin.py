"""Simple test for BibTeX export functionality in admin."""

import pytest
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


@pytest.mark.django_db
def test_bibtex_resource_export():
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Article",
        rok=2023,
    )

    resource = Wydawnictwo_CiagleBibTeXResource()
    queryset = Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo.pk)

    result = resource.export(queryset)

    assert result is not None
    assert "Test Article" in str(result)


def test_bibtex_format_properties():
    bibtex_format = BibTeXFormat()

    assert bibtex_format.get_title() == "BibTeX"
    assert bibtex_format.get_extension() == "bib"
    assert bibtex_format.can_export() is True
    assert bibtex_format.can_import() is False


def test_format_titles():
    bibtex_format = BibTeXFormat()
    xlsx_format = PrettyXLSX()

    assert bibtex_format.get_title() == "BibTeX"
    assert xlsx_format.get_title() == "prettyxlsx"


@pytest.mark.django_db
def test_patent_bibtex_resource_export():
    patent = baker.make(
        Patent,
        tytul_oryginalny="Test Patent",
        rok=2023,
    )

    resource = PatentBibTeXResource()
    queryset = Patent.objects.filter(pk=patent.pk)

    result = resource.export(queryset)

    assert result is not None
    assert "Test Patent" in str(result)


@pytest.mark.django_db
def test_praca_doktorska_bibtex_resource_export():
    praca_doktorska = baker.make(
        Praca_Doktorska,
        tytul_oryginalny="Test Doctoral Dissertation",
        rok=2023,
    )

    resource = Praca_DoktorskaBibTeXResource()
    queryset = Praca_Doktorska.objects.filter(pk=praca_doktorska.pk)

    result = resource.export(queryset)

    assert result is not None
    assert "Test Doctoral Dissertation" in str(result)


@pytest.mark.django_db
def test_praca_habilitacyjna_bibtex_resource_export():
    praca_habilitacyjna = baker.make(
        Praca_Habilitacyjna,
        tytul_oryginalny="Test Habilitation Thesis",
        rok=2023,
    )

    resource = Praca_HabilitacyjnaBibTeXResource()
    queryset = Praca_Habilitacyjna.objects.filter(pk=praca_habilitacyjna.pk)

    result = resource.export(queryset)

    assert result is not None
    assert "Test Habilitation Thesis" in str(result)
