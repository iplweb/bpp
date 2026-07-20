"""TYMCZASOWY dowód istnienia błędu — do usunięcia po naprawie."""

import pytest
from django.core.exceptions import MultipleObjectsReturned

from ewaluacja_metryki.models import StatusGenerowania


@pytest.mark.django_db
def test_dowod_dwa_nulle_lamia_get_or_create():
    StatusGenerowania.objects.create(uczelnia=None)
    StatusGenerowania.objects.create(uczelnia=None)

    assert StatusGenerowania.objects.filter(uczelnia__isnull=True).count() == 2

    with pytest.raises(MultipleObjectsReturned):
        StatusGenerowania.get_or_create()
