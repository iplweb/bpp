# -*- encoding: utf-8 -*-

import pytest
from django.core.files.base import File
from django.core.files.uploadedfile import SimpleUploadedFile
from model_mommy import mommy

from bpp.models.struktura import Wydzial
from egeria.models import EgeriaImport
from integrator2.models import ListaMinisterialnaIntegration
from mock import Mock
import os

@pytest.fixture
def test_file_path():
    test_file = os.path.join(
        os.path.dirname(__file__),
        'pracownicy.xlsx'
    )
    return test_file


@pytest.fixture
@pytest.mark.django_db
def egeria_import(test_file_path):

    test = EgeriaImport.objects.create(created_by=None)
    test.file = SimpleUploadedFile(test_file_path, open(test_file_path).read())
    test.save()
    return test

@pytest.fixture
@pytest.mark.django_db
def drugi_wydzial(uczelnia):
    drugi_wydzial = Wydzial.objects.create(
        nazwa="Inna nazwa",
        skrot="wtf",
        uczelnia=uczelnia)
    return drugi_wydzial
