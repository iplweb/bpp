"""Testy multi-hosted dla kolejki eksportu PBN.

Wpis kolejki niesie konkretną uczelnię (z entrypointu), żeby wysyłka w
tle użyła właściwej konfiguracji PBN zamiast zgadywać przez get_default().
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.tasks import queue_pbn_export_batch


@pytest.mark.django_db(transaction=True)
def test_queue_pbn_export_batch_stores_uczelnia(mocker, uczelnia):
    """Batch zapisuje uczelnię (z entrypointu) na wpisach kolejki."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="batch_user", password="testpass")
    record = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Rec")

    mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")

    queue_pbn_export_batch(
        app_label="bpp",
        model_name="wydawnictwo_ciagle",
        record_ids=[record.id],
        user_id=user.id,
        uczelnia_id=uczelnia.pk,
    )

    entry = PBN_Export_Queue.objects.get(zamowil=user)
    assert entry.uczelnia == uczelnia
