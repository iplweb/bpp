import os

import pytest
from django.core.files.base import File
from django.core.files.storage import default_storage
from model_mommy import mommy

from integrator2.models import ListaMinisterialnaIntegration

__dirname__ = os.path.dirname(__file__)


def test_file(name):
    return os.path.join(__dirname__, "xls", name)


def test_xls(name):
    return open(test_file(name), "rb")


@pytest.fixture
def lmi_base(db):
    lmi = mommy.make(ListaMinisterialnaIntegration)
    lmi.save()
    return lmi


def _make_lmi(_lmi, fn, fn2):
    path = default_storage.save(fn2, test_xls(fn))

    _lmi.file = File(default_storage.open(path))
    _lmi.save()
    return _lmi


@pytest.fixture
def lmi(lmi_base):
    return _make_lmi(lmi_base, "lista_a_krotka.xlsx", "a.xlsx")


@pytest.fixture
def lmi_b(lmi_base):
    return _make_lmi(lmi_base, "lista_b.xlsx", "b.xlsx")


@pytest.fixture
def lmi_c(lmi_base):
    return _make_lmi(lmi_base, "lista_c.xlsx", "c.xlsx")
