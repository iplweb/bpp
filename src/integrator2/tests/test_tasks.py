from datetime import timedelta

import pytest
from model_bakery import baker

from integrator2.models import ListaMinisterialnaIntegration
from integrator2.tasks import analyze_file, remove_old_integrator_files

from django.utils import timezone


@pytest.mark.django_db(transaction=True)
def test_analyze_file(lmi):
    res = analyze_file(pk=lmi.pk)
    assert res is None


@pytest.mark.django_db
def test_remove_old_integrator_files():
    baker.make(ListaMinisterialnaIntegration)
    f = baker.make(ListaMinisterialnaIntegration)
    f.uploaded_on = timezone.now() - timedelta(days=20)
    f.save()

    assert ListaMinisterialnaIntegration.objects.all().count() == 2

    remove_old_integrator_files()

    assert ListaMinisterialnaIntegration.objects.all().count() == 1
