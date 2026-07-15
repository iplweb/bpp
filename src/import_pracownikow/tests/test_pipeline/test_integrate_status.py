import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_WIELU
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_integracja_liczy_pominiete_brak_i_wielu():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    ImportPracownikowRow.objects.create(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_BRAK, autor=None
    )
    ImportPracownikowRow.objects.create(
        parent=imp, zmiany_potrzebne=False, confidence=STATUS_WIELU, autor=None
    )
    p = MockProgress(imp)
    integruj(imp, p)

    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    assert p.result_context["pominieto_niedopasowane"] == 2
    assert p.result_context["wymaga_uwagi"] is True
    # nietknięte — dalej bez autora
    assert imp.importpracownikowrow_set.filter(autor__isnull=True).count() == 2
