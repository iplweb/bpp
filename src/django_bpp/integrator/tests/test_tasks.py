# -*- encoding: utf-8 -*-
import pytest
from model_mommy import mommy
from integrator.models import IntegrationFile
from integrator.tasks import remove_old_integrator_files
from datetime import datetime, timedelta

@pytest.mark.django_db
def test_remove_old_integrator_files():
    mommy.make(IntegrationFile)
    f = mommy.make(IntegrationFile)
    f.uploaded_on = datetime.now() - timedelta(days=20)
    f.save()

    assert IntegrationFile.objects.all().count() == 2

    remove_old_integrator_files()

    assert IntegrationFile.objects.all().count() == 1