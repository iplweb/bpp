# -*- encoding: utf-8 -*-

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from bpp.models.struktura import Wydzial
from egeria.models import EgeriaImport


@pytest.fixture
def test_file_path():
    test_file = os.path.join(
        os.path.dirname(__file__),
        'pracownicy.xlsx'
    )
    return test_file


def _egeria_import_factory(path):
    test = EgeriaImport.objects.create(created_by=None)
    test.file = SimpleUploadedFile(path, open(path).read())
    test.save()
    return test

@pytest.fixture
@pytest.mark.django_db
def egeria_import(test_file_path):
    return _egeria_import_factory(test_file_path)


@pytest.fixture
@pytest.mark.django_db
def egeria_import_imported(test_file_path):
    egeria_import = _egeria_import_factory(test_file_path)
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
def wydzial_archiwalny(uczelnia):
    wydzial_archiwalny = Wydzial.objects.create(
        nazwa=u"Wydział Archiwalny",
        skrot="WArc",
        uczelnia=uczelnia,
        archiwalny=True)
    return wydzial_archiwalny
