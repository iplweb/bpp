import pytest
from django.core.files.base import File
from model_mommy import mommy
from integrator2.models import ListaMinisterialnaIntegration
from mock import Mock
import os

@pytest.fixture
def lmi(db):
    lmi = mommy.make(ListaMinisterialnaIntegration)
    lmi.save()

    lmi.file = File(open(os.path.dirname(__file__) + "/xls/lista_a_krotka.xlsx"))
    lmi.save()

    return lmi

@pytest.fixture
def lmi_b(lmi):
    lmi.file = File(open(os.path.dirname(__file__) + "/xls/lista_b.xlsx"))
    lmi.save()
    return lmi


@pytest.fixture
def lmi_c(lmi):
    lmi.file = File(open(os.path.dirname(__file__) + "/xls/lista_c.xlsx"))
    lmi.save()
    return lmi
