from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from bpp.models import Zrodlo
from import_list_if.models import ImportListIf


@pytest.fixture
def testdata_xlsx_path():
    import os

    return os.path.join(os.path.dirname(__file__), "testdata1.xlsx")


def import_list_if_factory(user, path, rok):
    i = ImportListIf(owner=user, rok=rok)
    i.plik_xls = SimpleUploadedFile(
        "import_dyscyplin_zrodel_przyklad.xlsx", open(path, "rb").read()
    )
    i.save()
    return i


@pytest.fixture
def import_list_if(admin_user, testdata_xlsx_path, zrodlo, rok):
    zrodlo.nazwa = "Gazeta"
    zrodlo.save()

    return import_list_if_factory(admin_user, testdata_xlsx_path, rok)


def test_ImportListIF_perform(import_list_if, rok):
    import_list_if.perform()
    assert import_list_if.importlistifrow_set.count() == 4
    assert Zrodlo.objects.get(nazwa="Gazeta").punktacja_zrodla_set.get(
        rok=rok
    ).impact_factor == Decimal("70.67")


def test_ImportListIF_on_reset(import_list_if, rok):
    import_list_if.on_reset()
    assert True


def test_ImportListIF_get_details_set(import_list_if, rok):
    import_list_if.get_details_set()
    assert True
