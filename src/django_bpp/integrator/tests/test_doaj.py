# -*- encoding: utf-8 -*-
import os
from model_mommy import mommy
import pytest
from integrator.doaj import read_doaj_csv_data, doaj_import_data
from integrator.models import IntegrationFile, INTEGRATOR_ATOZ, ZrodloIntegrationRecord

integrator_test1_csv = os.path.join(
    os.path.dirname(__file__),
    "integrator.doaj.test1.csv")

def test_atoz_read():
    l = list(read_doaj_csv_data(open(integrator_test1_csv)))
    assert len(l) == 58

@pytest.mark.django_db
def test_atoz_import():
    parent = mommy.make(IntegrationFile, type=INTEGRATOR_ATOZ)
    doaj_import_data(parent, read_doaj_csv_data(open(integrator_test1_csv)))

    assert ZrodloIntegrationRecord.objects.filter(parent=parent).count() == 58