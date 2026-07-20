"""Testy migracji importów POLON/absencji na django-liveops.

Pokrywają: finalizację ``run(self, p)`` (MockProgress), renderowanie strony
live (host template + wrapper CSRF) oraz gejtowany grupą restart.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.files import File
from django.urls import reverse
from liveops.testing import MockProgress
from model_bakery import baker

from import_polon.models import (
    ImportPlikuAbsencji,
    ImportPlikuPolon,
    WierszImportuPlikuPolon,
)

GRUPA = "wprowadzanie danych"


# --- run() finalizuje operację ----------------------------------------------


@pytest.mark.django_db
def test_run_finalizuje_polon(admin_user, fn_test_import_polon):
    imp = baker.make(
        ImportPlikuPolon, owner=admin_user, rok=2023, zapisz_zmiany_do_bazy=False
    )
    with open(fn_test_import_polon, "rb") as f:
        imp.plik.save("test_import_polon.xlsx", File(f))

    imp.run(MockProgress(imp))

    imp.refresh_from_db()
    assert imp.finished_successfully is True
    n = imp.get_details_set().count()
    assert n > 0, "run() musi utworzyć wiersze-dzieci"
    assert imp.result_context == {"total": n}


@pytest.mark.django_db
def test_run_finalizuje_absencji(admin_user, fn_test_import_absencji):
    imp = baker.make(ImportPlikuAbsencji, owner=admin_user, zapisz_zmiany_do_bazy=False)
    with open(fn_test_import_absencji, "rb") as f:
        imp.plik.save("test_import_absencji.xlsx", File(f))

    imp.run(MockProgress(imp))

    imp.refresh_from_db()
    assert imp.finished_successfully is True
    n = imp.get_details_set().count()
    assert n > 0
    assert imp.result_context == {"total": n}


# --- strona live (host template + wrapper CSRF) -----------------------------


@pytest.mark.django_db
def test_liveops_live_view_renderuje_host(admin_client, admin_user):
    imp = baker.make(ImportPlikuPolon, owner=admin_user, rok=2023)

    assert imp.get_absolute_url() == (f"/live/import_polon.importplikupolon/{imp.pk}/")

    response = admin_client.get(imp.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    # kontener liveops (WS binding)
    assert "data-liveop-channel" in content
    assert "data-liveop-token" in content
    # wrapper CSRF (CSRF_COOKIE_HTTPONLY=True → X-CSRFToken przez hx-headers)
    assert "X-CSRFToken" in content


@pytest.mark.django_db
def test_liveops_live_view_absencji_url(admin_user):
    imp = baker.make(ImportPlikuAbsencji, owner=admin_user)
    assert imp.get_absolute_url() == (
        f"/live/import_polon.importplikuabsencji/{imp.pk}/"
    )


# --- restart gejtowany grupą (precedens #508 F4) ----------------------------


def _polon_z_wierszami(owner):
    """Zakończony pomyślnie import POLON z dwoma wierszami-dziećmi (bez pliku —
    ponowny run i tak by padł, ale nas interesuje wyłącznie efekt uboczny
    bramki: czy wiersze-dzieci zostały skasowane / operacja zresetowana)."""
    from django.utils import timezone

    imp = baker.make(
        ImportPlikuPolon,
        owner=owner,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
    )
    baker.make(WierszImportuPlikuPolon, parent=imp, nr_wiersza=1)
    baker.make(WierszImportuPlikuPolon, parent=imp, nr_wiersza=2)
    return imp


@pytest.mark.django_db
def test_restart_bez_grupy_nie_zmienia_stanu(client, django_user_model):
    u = django_user_model.objects.create_user(username="plain-restart", password="x")
    client.force_login(u)
    imp = _polon_z_wierszami(u)
    url = reverse("import_polon:importplikupolon-restart", kwargs={"pk": imp.pk})

    resp = client.post(url)

    # GroupRequiredMixin ma raise_exception=False → 302 (redirect_to_login),
    # NIE 403. Kluczowe: brak efektu ubocznego.
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.finished_successfully is True, "operacja NIE mogła zostać zresetowana"
    assert imp.wierszimportuplikupolon_set.count() == 2, "wiersze-dzieci nietknięte"


@pytest.mark.django_db
def test_restart_z_grupa_przechodzi(client, django_user_model):
    u = django_user_model.objects.create_user(username="entry-restart", password="x")
    u.groups.add(Group.objects.get_or_create(name=GRUPA)[0])
    client.force_login(u)
    imp = _polon_z_wierszami(u)
    url = reverse("import_polon:importplikupolon-restart", kwargs={"pk": imp.pk})

    client.post(url)

    imp.refresh_from_db()
    # Bramka przeszła: on_restart() skasował wiersze-dzieci, a reset zdjął
    # znacznik pomyślnego zakończenia (ponowny run bez pliku kończy się błędem).
    assert imp.wierszimportuplikupolon_set.count() == 0
    assert imp.finished_successfully is False
