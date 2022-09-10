import pytest
from django.core.files.base import File
from model_bakery import baker

from ewaluacja2021.models import ImportMaksymalnychSlotow
from ewaluacja2021.tests.utils import curdir

from bpp.models import Dyscyplina_Naukowa


@pytest.mark.django_db
def test_ImportMaksymalnychSlotow_analizuj(autor_jan_kowalski):
    baker.make(Dyscyplina_Naukowa, nazwa="nauki farmaceutyczne")

    ims = ImportMaksymalnychSlotow.objects.create()
    ims.plik.save("test.xlsx", File(open(curdir("test_file.xlsx", __file__), "rb")))
    ims.analizuj()

    assert ims.przeanalizowany
    assert ims.wierszimportumaksymalnychslotow_set.filter(poprawny=True).count() == 1
    assert (
        ims.wierszimportumaksymalnychslotow_set.filter(wymagana_integracja=True).count()
        == 1
    )
    assert ims.wierszimportumaksymalnychslotow_set.filter(poprawny=False).count() == 1
