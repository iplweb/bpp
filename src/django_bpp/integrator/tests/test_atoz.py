# -*- encoding: utf-8 -*

import os
from model_mommy import mommy
import pytest
from integrator.atoz import read_atoz_xls_data, atoz_import_data
from integrator.doaj import zrodlo_integrate_data, zrodlo_analyze_data
from integrator.models import IntegrationFile, INTEGRATOR_ATOZ, ZrodloIntegrationRecord

integrator_test1_xlsx = os.path.join(
    os.path.dirname(__file__),
    "integrator.atoz.test1.xlsx")


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
