from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from integrator2.models import ListaMinisterialnaIntegration
from integrator2.tasks import analyze_file, remove_old_integrator_files


@pytest.mark.django_db(transaction=True)
def test_analyze_file(lmi):
    # Wait_for_object używany przez analyze_file wymaga kontekstu
    # celery (current_task.retry), dlatego zadanie wołamy przez
    # .delay() (eager mode wykonuje je synchronicznie).
    res = analyze_file.delay(pk=lmi.pk).get()
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
