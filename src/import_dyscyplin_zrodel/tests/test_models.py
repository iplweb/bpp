import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_mommy import mommy

from bpp.models import Dyscyplina_Naukowa, Zrodlo
from import_dyscyplin_zrodel.models import (
    ImportDyscyplinZrodel,
    ImportDyscyplinZrodelRow,
)


@pytest.fixture
def testdata_path():
    import os

    return os.path.join(os.path.dirname(__file__), "testdata.xlsx")


@pytest.fixture
def import_dyscyplin_zrodel(testdata_path, admin_user):

    i = ImportDyscyplinZrodel(owner=admin_user)
    i.plik_xls = SimpleUploadedFile(
        "import_dyscyplin_zrodel_przyklad.xlsx", open(testdata_path, "rb").read()
    )
    i.save()
    return i


def test_ImportDyscyplinZrodel_perform(import_dyscyplin_zrodel):
    z = mommy.make(Zrodlo, nazwa="2D Materials")
    mommy.make(Dyscyplina_Naukowa, nazwa="architektura i urbanistyka", kod="2.1")
    mommy.make(Dyscyplina_Naukowa, nazwa="nauki fizyczne", kod="6.6")

    import_dyscyplin_zrodel.perform()

    assert ImportDyscyplinZrodelRow.objects.count() == 14

    first = ImportDyscyplinZrodelRow.objects.first()
    assert first.zrodlo == z
    assert first.importdyscyplinzrodelrowdyscypliny_set.all().count() == 2
