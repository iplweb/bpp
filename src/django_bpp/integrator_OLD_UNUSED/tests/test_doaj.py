# -*- encoding: utf-8 -*-
import os

import pytest
from model_mommy import mommy

from integrator2.models import IntegrationFile, INTEGRATOR_ATOZ, ZrodloIntegrationRecord
from integrator_OLD_UNUSED import read_doaj_csv_data, doaj_import_data

integrator_test1_csv = os.path.join(
    os.path.dirname(__file__),
        "../../tests/xls/integrator_OLD_UNUSED.doaj.test1.csv")

def test_atoz_read():
    l = list(read_doaj_csv_data(open(integrator_test1_csv)))
    assert len(l) == 6

@pytest.mark.django_db
def test_atoz_import():
    parent = mommy.make(IntegrationFile, type=INTEGRATOR_ATOZ)
    doaj_import_data(parent, read_doaj_csv_data(open(integrator_test1_csv)))

    assert ZrodloIntegrationRecord.objects.filter(parent=parent).count() == 6