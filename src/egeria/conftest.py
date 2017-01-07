# -*- encoding: utf-8 -*-

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse

from bpp.models.struktura import Wydzial
from egeria.models import EgeriaImport


@pytest.fixture
def test_file_path():
    test_file = os.path.join(
        os.path.dirname(__file__),
        'pracownicy.xlsx'
    )
    return test_file


def _egeria_import_factory(path, uczelnia):
    test = EgeriaImport.objects.create(created_by=None, uczelnia=uczelnia)
    test.file = SimpleUploadedFile(path, open(path).read())
    test.save()
    return test


@pytest.fixture
@pytest.mark.django_db
def egeria_import(test_file_path, uczelnia):
    return _egeria_import_factory(test_file_path, uczelnia)


@pytest.fixture
@pytest.mark.django_db
def egeria_import_imported(test_file_path, uczelnia):
    egeria_import = _egeria_import_factory(test_file_path, uczelnia)
    egeria_import.everything()
    return egeria_import


@pytest.fixture
@pytest.mark.django_db
def drugi_wydzial(uczelnia):
    drugi_wydzial = Wydzial.objects.create(
        nazwa="Inna nazwa",
        skrot="wtf",
        uczelnia=uczelnia)
    return drugi_wydzial


@pytest.fixture
@pytest.mark.django_db
def first_page_after_upload(admin_app, test_file_path):
    page = admin_app.get(reverse("egeria:new"))
    res = page.form.submit(upload_files=[('file', test_file_path)]).maybe_follow()
    return res


@pytest.fixture
@pytest.mark.django_db
def egeria_browser_detail(preauth_browser, live_server, egeria_import):
    """
    Zwraca zalogowaną przeglądarkę WWW (Selenium poprzez splitnera),
    otwarta strona to widok szczegółów zaimportowanego pliku XLS,
    gdzie plik XLS do importu został już wstępnie przeanalizowany.
        :return:
    """

    egeria_import.analyze()
    egeria_import.next_import_step()
    # Selenium
    preauth_browser.visit(live_server + reverse("egeria:detail", args=(egeria_import.pk,)))
    return preauth_browser
