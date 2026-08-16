"""Kasowanie sesji importu, do której powstały wpisy dziennika.

``ImportLog.session`` ma FK do ``ImportSession`` z ``CASCADE``, a
``ImportLogAdmin.has_delete_permission`` zwracał twarde ``False``. Django pyta
tą samą metodą o uprawnienia do obiektów kasowanych kaskadowo
(``django.contrib.admin.utils.get_deleted_objects``), więc odmowa pomyślana
jako „dziennik jest tylko do odczytu" blokowała skasowanie samej sesji --
również superuserowi. A każdy wykonany import wpisy dziennika produkuje, więc
nieusuwalna była w praktyce każda sesja, która się odbyła.
"""

import pytest
from django.contrib.admin import site
from django.urls import reverse

from pbn_import.models import ImportLog, ImportSession


@pytest.fixture
def sesja_importu(db, admin_user):
    sesja = ImportSession.objects.create(user=admin_user, status="completed")
    ImportLog.objects.create(
        session=sesja, level="info", step="pobieranie", message="Start importu"
    )
    ImportLog.objects.create(
        session=sesja, level="error", step="zapis", message="Coś poszło nie tak"
    )
    return sesja


@pytest.mark.django_db
def test_admin_kasuje_sesje_importu_z_dziennikiem(admin_client, sesja_importu):
    pk = sesja_importu.pk

    res = admin_client.post(
        reverse("admin:pbn_import_importsession_delete", args=[pk]),
        {"post": "yes"},
    )

    assert res.status_code == 302
    assert not ImportSession.objects.filter(pk=pk).exists()
    assert not ImportLog.objects.filter(session_id=pk).exists()


@pytest.mark.django_db
def test_dziennik_importu_pozostaje_niedopisywalny(admin_client):
    """Odblokowaliśmy kasowanie — dziennik nadal ma być nie do podrobienia."""
    ma = site.get_model_admin(ImportLog)
    request = admin_client.request(PATH_INFO="/").wsgi_request

    assert ma.has_add_permission(request) is False
