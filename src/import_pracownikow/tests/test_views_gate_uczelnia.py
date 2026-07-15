"""Bramka „brak uczelni z requestu" + scoping obiektów do bieżącej uczelni.

Multi-hosted: import działa TYLKO w zakresie uczelni z requestu. Brak uczelni
(domena bez mapowania Site→Uczelnia, >1 uczelnia) → redirect na home dla
WSZYSTKICH (też superusera). Obcy import (inna uczelnia) → 404.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tests._helpers import ustaw_biezaca_uczelnie


@pytest.mark.django_db
def test_lista_redirect_gdy_brak_uczelni(admin_client):
    """>1 uczelnia + żadna nie zmapowana na host → lista redirectuje na home."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # get_for_request → None (brak mapowania, >1)
    resp = admin_client.get(reverse("import_pracownikow:index"))
    assert resp.status_code == 302
    assert resp.url == "/"


@pytest.mark.django_db
def test_lista_ok_gdy_uczelnia_zmapowana(admin_client, settings):
    """Uczelnia zmapowana na host klienta → lista działa (200)."""
    u = baker.make(Uczelnia)
    baker.make(Uczelnia)  # druga, ale host wskazuje na u
    host = ustaw_biezaca_uczelnie(u, settings)
    resp = admin_client.get(reverse("import_pracownikow:index"), HTTP_HOST=host)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lista_scoped_do_biezacej_uczelni(admin_client, admin_user, settings):
    """Lista pokazuje tylko importy bieżącej uczelni (nie innej)."""
    u = baker.make(Uczelnia)
    inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    moj = baker.make(ImportPracownikow, owner=admin_user, uczelnia=u)
    baker.make(ImportPracownikow, owner=admin_user, uczelnia=inna)
    resp = admin_client.get(reverse("import_pracownikow:index"), HTTP_HOST=host)
    assert list(resp.context["object_list"]) == [moj]
