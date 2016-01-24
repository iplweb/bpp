# -*- encoding: utf-8 -*

import os

import pytest
from integrator2.doaj import zrodlo_integrate_data, zrodlo_analyze_data
from model_mommy import mommy

from integrator2.models import IntegrationFile, INTEGRATOR_ATOZ, ZrodloIntegrationRecord
from integrator_OLD_UNUSED.atoz import read_atoz_xls_data, atoz_import_data

integrator_test1_xlsx = os.path.join(
    os.path.dirname(__file__),
        "../../tests/xls/integrator_OLD_UNUSED.atoz.test1.xlsx")


def test_atoz_read():
    l = list(read_atoz_xls_data(open(integrator_test1_xlsx)))
    assert len(l) == 13

@pytest.mark.django_db
def test_atoz_import():
    parent = mommy.make(IntegrationFile, type=INTEGRATOR_ATOZ)
    atoz_import_data(parent, read_atoz_xls_data(open(integrator_test1_xlsx)))

    assert ZrodloIntegrationRecord.objects.filter(parent=parent).count() == 13


@pytest.mark.django_db
def test_atoz_integrate():
    parent = mommy.make(IntegrationFile, type=INTEGRATOR_ATOZ)
    atoz_import_data(parent, read_atoz_xls_data(open(integrator_test1_xlsx)))
    zrodlo_analyze_data(parent)
    zrodlo_integrate_data(parent)
