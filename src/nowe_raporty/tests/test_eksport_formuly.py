from io import BytesIO

import openpyxl
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from flexible_reports.models import (
    DATA_FROM_DATASOURCE,
    Column,
    Datasource,
    ReportElement,
    Table,
)
from flexible_reports.models.report import Report
from model_bakery import baker

from bpp.models.cache import Rekord
from nowe_raporty.models import DefinicjaRaportu

FORMULA = '=HYPERLINK("http://x","y")'


@pytest.mark.django_db
def test_eksport_xlsx_tytul_jako_tekst(
    uczelnia,
    autor_jan_kowalski,
    client,
    jednostka,
    wydawnictwo_ciagle,
    typ_odpowiedzialnosci_autor,
):
    wydawnictwo_ciagle.tytul_oryginalny = FORMULA
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    rok = wydawnictwo_ciagle.rok

    r = baker.make(Report, slug="raport-autorow")
    baker.make(
        DefinicjaRaportu,
        slug="raport-autorow",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=r,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
        aktywny=True,
    )
    ds = baker.make(Datasource, dsl_query=f"rok = {rok}", distinct=True)
    base_model = ContentType.objects.get_for_model(Rekord)
    t = baker.make(Table, base_model=base_model)
    baker.make(Column, parent=t, attr_name="tytul_oryginalny")
    baker.make(
        ReportElement,
        parent=r,
        data_from=DATA_FROM_DATASOURCE,
        base_model=base_model,
        datasource=ds,
        table=t,
    )

    url = (
        reverse(
            "nowe_raporty:raport_generuj",
            args=("raport-autorow", autor_jan_kowalski.pk, rok, rok),
        )
        + "?_export=xlsx&_tzju=True"
    )
    res = client.get(url)

    ws = openpyxl.load_workbook(BytesIO(res.content)).worksheets[0]
    komorki = [c for row in ws.iter_rows(min_row=2) for c in row]
    assert any(c.value == "'" + FORMULA for c in komorki)
    assert all(c.data_type != "f" for c in komorki)
