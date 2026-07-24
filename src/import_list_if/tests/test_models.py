from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.progress import OperationCancelled
from liveops.testing import MockProgress

from bpp.models import Zrodlo
from import_list_if.models import ImportListIf


@pytest.fixture
def testdata_xlsx_path():
    import os

    return os.path.join(os.path.dirname(__file__), "testdata1.xlsx")


def import_list_if_factory(user, path, rok):
    i = ImportListIf(owner=user, rok=rok)
    with open(path, "rb") as f:
        i.plik_xls = SimpleUploadedFile(
            "import_dyscyplin_zrodel_przyklad.xlsx", f.read()
        )
    i.save()
    return i


@pytest.fixture
def import_list_if(admin_user, testdata_xlsx_path, zrodlo, rok):
    zrodlo.nazwa = "Gazeta"
    zrodlo.save()

    return import_list_if_factory(admin_user, testdata_xlsx_path, rok)


def test_ImportListIF_run(import_list_if, rok):
    import_list_if.run(MockProgress(import_list_if))
    assert import_list_if.importlistifrow_set.count() == 4
    assert Zrodlo.objects.get(nazwa="Gazeta").punktacja_zrodla_set.get(
        rok=rok
    ).impact_factor == Decimal("70.67")
    assert import_list_if.result_context["total"] == 4


def test_ImportListIF_run_finalizuje_operacje(import_list_if):
    import_list_if.run(MockProgress(import_list_if))
    import_list_if.refresh_from_db()
    assert import_list_if.finished_on is not None
    assert import_list_if.finished_successfully is True


def test_ImportListIF_run_anulowanie_cofa_wiersze(import_list_if):
    # Owinięcie run() w transaction.atomic() sprawia, że OperationCancelled
    # cofa (rollback) już zapisane wiersze — parytet z legacy task_perform.
    with pytest.raises(OperationCancelled):
        import_list_if.run(MockProgress(import_list_if, cancel_after=1))
    assert import_list_if.importlistifrow_set.count() == 0


def test_ImportListIF_on_restart(import_list_if, rok):
    import_list_if.run(MockProgress(import_list_if))
    assert import_list_if.importlistifrow_set.count() == 4
    import_list_if.on_restart()
    assert import_list_if.importlistifrow_set.count() == 0


def test_ImportListIF_get_details_set(import_list_if, rok):
    import_list_if.get_details_set()
    assert True
