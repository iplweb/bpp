from unittest.mock import patch

import pytest


@pytest.fixture
def bez_celery():
    """Odcina realną wysyłkę do PBN z receiverów fazy 06.

    Kolejkowanie kończy się ``task_sprobuj_wyslac_do_pbn.delay()``, a testy
    biegną z ``CELERY_TASK_ALWAYS_EAGER = True`` (``settings/test.py``) —
    bez tej atrapy zadanie wykonałoby się synchronicznie, w środku
    ``delete()``/``restore()``, i próbowało pogadać z PBN-em.
    """
    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn") as mock_task:
        yield mock_task
