"""Widoczność błędów importu pracowników i jednostek.

Regresja operacji ``bd90660e``: import padł na pustym wierszu XLS, ale
`liveops.runner._handle_error` zapisuje traceback WYŁĄCZNIE do bazy (pole
`traceback`) — bez śladu na konsoli workera ani w rollbarze, a admin nie miał
żadnego widoku operacji importu. Te testy pilnują, że:

1. wyjątek w ``run()`` trafia na rollbar (i konsolę) i jest re-raise'owany,
2. model ``ImportPracownikow`` jest zarejestrowany w adminie i pokazuje traceback.
"""

import sys

import pytest
from django.urls import reverse
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_run_zglasza_wyjatek_na_rollbar_i_reraise(admin_user, monkeypatch):
    """Wyjątek w ``run()`` MUSI trafić na rollbar (i konsolę) oraz zostać
    re-raise'owany — inaczej liveops chowa go tylko do bazy i ani user, ani
    monitoring nic nie widzi."""
    zgloszenia = []
    monkeypatch.setattr(
        "rollbar.report_exc_info",
        lambda *a, **k: zgloszenia.append(sys.exc_info()[1]),
    )

    def wybuchnij(*a, **k):
        raise ValueError("boom-testowy")

    # run() robi lokalny `from ...analyze import analizuj`, więc patchujemy
    # atrybut modułu (resolved w momencie wywołania).
    monkeypatch.setattr("import_pracownikow.pipeline.analyze.analizuj", wybuchnij)

    op = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_ZMAPOWANY
    )
    with pytest.raises(ValueError, match="boom-testowy"):
        op.run(MockProgress(op))

    assert zgloszenia, "rollbar.report_exc_info nie został wywołany"
    assert isinstance(zgloszenia[0], ValueError)


@pytest.mark.django_db
def test_run_sukces_nie_dotyka_rollbara(
    admin_user, monkeypatch, baza_importu_pracownikow, testdata_xlsx_path
):
    """Poprawny przebieg nie zgłasza niczego na rollbar (brak fałszywych alarmów)."""
    zgloszenia = []
    monkeypatch.setattr(
        "rollbar.report_exc_info", lambda *a, **k: zgloszenia.append(True)
    )
    from import_pracownikow.tests.conftest import import_pracownikow_factory

    op = import_pracownikow_factory(admin_user, testdata_xlsx_path)
    op.stan = ImportPracownikow.STAN_ZMAPOWANY
    op.run(MockProgress(op))

    assert not zgloszenia


@pytest.mark.django_db
def test_admin_import_pracownikow_zarejestrowany(admin_client):
    """Changelista operacji importu ładuje się (model zarejestrowany w adminie)."""
    url = reverse("admin:import_pracownikow_importpracownikow_changelist")
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_wiersze_importu_zarejestrowane(admin_client):
    """Changelista wierszy (rezultatów) importu ładuje się (drill-down)."""
    url = reverse("admin:import_pracownikow_importpracownikowrow_changelist")
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_import_pokazuje_traceback(admin_client, admin_user):
    """Widok szczegółów operacji pokazuje traceback (diagnoza bez zaglądania do bazy)."""
    op = baker.make(
        ImportPracownikow,
        owner=admin_user,
        traceback="MARKER-TRACEBACK-123",
    )
    url = reverse("admin:import_pracownikow_importpracownikow_change", args=[op.pk])
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"MARKER-TRACEBACK-123" in resp.content
