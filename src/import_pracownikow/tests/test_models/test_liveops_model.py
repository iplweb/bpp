import pytest
from liveops.models import LiveOperation
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_jest_liveoperation_z_polem_stan():
    imp = baker.make(ImportPracownikow)
    assert isinstance(imp, LiveOperation)
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
    # pola po long_running zniknęły:
    assert not hasattr(imp, "performed")
    assert not hasattr(imp, "integrated")


@pytest.mark.django_db
def test_run_dispatch_po_stanie(monkeypatch):
    wywolane = []
    monkeypatch.setattr(
        "import_pracownikow.pipeline.analyze.analizuj",
        lambda parent, p: wywolane.append("analiza"),
    )
    monkeypatch.setattr(
        "import_pracownikow.pipeline.integrate.integruj",
        lambda parent, p: wywolane.append("integracja"),
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.run(p=object())
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.run(p=object())
    imp.stan = ImportPracownikow.STAN_ZINTEGROWANY

    class _P:
        def log(self, s):
            wywolane.append(f"log:{s}")

    imp.run(p=_P())
    assert wywolane[0] == "analiza"
    assert wywolane[1] == "integracja"
    assert wywolane[2].startswith("log:")  # no-op z logiem
