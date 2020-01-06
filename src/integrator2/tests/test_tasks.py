# -*- encoding: utf-8 -*-
from datetime import datetime, timedelta

import pytest
from model_mommy import mommy

from integrator2.models import ListaMinisterialnaIntegration
from integrator2.tasks import remove_old_integrator_files, analyze_file
from django.utils import timezone

@pytest.mark.django_db
def test_analyze_file(lmi):
    res = analyze_file(pk=lmi.pk)
    assert res is None

@pytest.mark.django_db
def test_remove_old_integrator_files():
    mommy.make(ListaMinisterialnaIntegration)
    f = mommy.make(ListaMinisterialnaIntegration)
    f.uploaded_on = timezone.now() - timedelta(days=20)
    f.save()

    assert ListaMinisterialnaIntegration.objects.all().count() == 2

    remove_old_integrator_files()

    assert ListaMinisterialnaIntegration.objects.all().count() == 1
