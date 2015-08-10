# -*- encoding: utf-8 -*-

from django.core.urlresolvers import reverse
from webtest import Upload
import os
from integrator.models import AUTOR_IMPORT_COLUMNS
from integrator.tasks import read_xls_data, read_autor_import

integrator_test1_xlsx = os.path.join(
    os.path.dirname(__file__),
    "integrator.test1.xlsx")


def test_upload(preauth_webtest_app, normal_django_user):
    page = preauth_webtest_app.get(reverse('integrator:new'))
    form = page.form
    form['file'] = Upload(integrator_test1_xlsx)
    res = form.submit().maybe_follow()
    assert "Plik został dodany" in res.content

def test_read_xls_data():
    file_contents = open(integrator_test1_xlsx, "rb").read()
    data = read_autor_import(file_contents)
    data = list(data)
    assert data[0]['nazwisko'] == 'Kowalski'
    assert len(data) == 4