import os

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from webtest.forms import Upload


@pytest.mark.django_db
def test_serwer_testowy(client):
    # W przypadku, gdy domena zawiera słowo "test", to na stronie powinien
    # pojawić się obrazek tła oraz słowo "SERWER TESTOWY" w tytule
    response = client.get("/", SERVER_NAME="test.unexistenttld")
    assert b"<b>Serwer testowy" in response.content

    response = client.get("/", SERVER_NAME="127.0.0.1")
    assert b"<b>Serwer testowy" not in response.content


def test_views_main(admin_client):
    res = admin_client.get(reverse("integrator2:main"))
    assert "Brak plików" in res.rendered_content


def test_views_upload_lista_ministerialna(admin_app):
    page = admin_app.get(reverse("integrator2:upload_lista_ministerialna"))

    form = page.form
    form["file"] = Upload(os.path.dirname(__file__) + "/xls/lista_a_krotka.xlsx")
    res = form.submit().maybe_follow()

    assert "Plik został dodany" in res.text


def test_views_detail(admin_app, admin_user, lmi):
    lmi.owner = admin_user
    lmi.save()

    url = reverse("integrator2:detail", args=(lmi._meta.model_name, lmi.pk))
    page = admin_app.get(url)

    assert b"xlsx" in page.content
