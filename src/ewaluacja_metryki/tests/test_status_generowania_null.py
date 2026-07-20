"""Regresja: `StatusGenerowania` z `uczelnia IS NULL` musi być singletonem.

W PostgreSQL NULL-e w indeksie unikalnym są wzajemnie rozróżnialne, więc
`OneToOneField(null=True)` NIE ogranicza liczby wierszy z `uczelnia IS NULL`.
Dwa równoległe żądania mogły utworzyć dwa takie wiersze, a od tej chwili każde
`StatusGenerowania.get_or_create()` (bez argumentu) rzucało
`MultipleObjectsReturned` → trwałe 500 aż do ręcznego sprzątnięcia bazy.
"""

import pytest
from django.db import IntegrityError, transaction

from ewaluacja_metryki.models import StatusGenerowania


@pytest.mark.django_db
def test_drugi_status_bez_uczelni_odrzucony_przez_baze():
    """Partial unique index dopuszcza co najwyżej jeden wiersz z NULL-em."""
    StatusGenerowania.objects.create(uczelnia=None)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StatusGenerowania.objects.create(uczelnia=None)


@pytest.mark.django_db
def test_get_or_create_bez_argumentu_jest_idempotentne():
    """Powtórzone wywołanie bez argumentu zwraca ten sam wiersz, nie wyjątek."""
    pierwszy = StatusGenerowania.get_or_create()
    drugi = StatusGenerowania.get_or_create()

    assert pierwszy.pk == drugi.pk
    assert StatusGenerowania.objects.filter(uczelnia__isnull=True).count() == 1
