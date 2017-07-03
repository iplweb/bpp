# -*- encoding: utf-8 -*-


import os

from django.core.urlresolvers import reverse
from webtest.forms import Upload


def test_views_main(admin_client):
    res = admin_client.get(reverse("integrator2:main"))
    assert b"Brak plików" in res.content


def test_views_upload_lista_ministerialna(admin_app):
    page = admin_app.get(reverse("integrator2:upload_lista_ministerialna"))

    form = page.form
    form['file'] = Upload(os.path.dirname(__file__) + "/xls/lista_a_krotka.xlsx")
    res = form.submit().maybe_follow()

    assert b"Plik został dodany" in res.content


def test_views_detail(admin_app, admin_user, lmi):
    lmi.owner = admin_user
    lmi.save()

    url = reverse("integrator2:detail", args=(lmi._meta.model_name, lmi.pk))
    page = admin_app.get(url)

    assert b'xlsx' in page.content
