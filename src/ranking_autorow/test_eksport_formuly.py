from io import BytesIO

import openpyxl
from django.urls import reverse

from bpp.models import Autor
from bpp.tests.util import CURRENT_YEAR
from ranking_autorow.tests import ranking_data  # noqa: F401
from ranking_autorow.views import RankingAutorow

FORMULA = '=HYPERLINK("http://x","y")'


def test_ranking_uzywa_bezpiecznego_eksportu():
    from bpp.export.tables2 import BezpiecznyTableExport

    assert RankingAutorow.export_class is BezpiecznyTableExport


def test_ranking_eksport_xlsx_autor_jako_tekst(ranking_data):  # noqa: F811
    Autor.objects.update(nazwisko=FORMULA)
    client = ranking_data["client"]

    response = client.get(
        reverse("bpp:ranking-autorow", args=(str(CURRENT_YEAR), str(CURRENT_YEAR)))
        + "?_export=xlsx",
        follow=True,
    )

    ws = openpyxl.load_workbook(BytesIO(response.content)).active
    komorki = [c for row in ws.iter_rows(min_row=2) for c in row]
    assert any(
        isinstance(c.value, str) and c.value.startswith("'" + FORMULA) for c in komorki
    )
    assert all(c.data_type != "f" for c in komorki)
