import os

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.test import override_settings
from webtest.forms import Upload


@pytest.mark.django_db
def test_serwer_testowy(client):
    # Test when DJANGO_BPP_ENABLE_TEST_CONFIGURATION is enabled
    with override_settings(DJANGO_BPP_ENABLE_TEST_CONFIGURATION=True):
        response = client.get("/")
        assert b"SERWER TESTOWY - ZMIANY MOG" in response.content

    # Test when DJANGO_BPP_ENABLE_TEST_CONFIGURATION is disabled (default)
    with override_settings(DJANGO_BPP_ENABLE_TEST_CONFIGURATION=False):
        response = client.get("/")
        assert b"SERWER TESTOWY - ZMIANY MOG" not in response.content


def test_views_main(admin_client):
    res = admin_client.get(reverse("integrator2:main"))
    assert "Brak plików" in res.rendered_content


def test_views_upload_lista_ministerialna(admin_app):
    page = admin_app.get(reverse("integrator2:upload_lista_ministerialna"))

    # Find the upload form (not the logout form)
    form = None
    for f in page.forms.values():
        if "file" in f.fields:
            form = f
            break

    assert form is not None, "Could not find upload form"

    form["file"] = Upload(os.path.dirname(__file__) + "/xls/lista_a_krotka.xlsx")
    res = form.submit().maybe_follow()

    assert "Plik został dodany" in res.text


def test_views_detail(admin_app, admin_user, lmi):
    lmi.owner = admin_user
    lmi.save()

    url = reverse("integrator2:detail", args=(lmi._meta.model_name, lmi.pk))
    page = admin_app.get(url)

    assert b"xlsx" in page.content
