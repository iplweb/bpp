"""FD#633: generowanie metryk, które WYSTARTOWAŁO i padło w trakcie
(restart workera, ubity proces), wisiało jako „w trakcie” bez końca.
FD#630 objęło tylko przebieg, który w ogóle nie ruszył."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia
from ewaluacja_common.przebiegi import MARTWY
from ewaluacja_metryki.models import StatusGenerowania

from .conftest import wybierz_okres

pytestmark = pytest.mark.django_db

POWOD = "ewaluacja_common.przebiegi.powod_przerwania"
PRZYCISK_AKTYWNY = 'data-open="generowanie-modal"'
PRZYCISK_ZABLOKOWANY = "Generowanie w trakcie"


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


def _w_polowie(uczelnia, okres, wiek=3600):
    """Generowanie, które ruszyło i przetworzyło część autorów."""
    status = StatusGenerowania.get_or_create(uczelnia=uczelnia, okres=okres)
    status.rozpocznij_generowanie(
        task_id="zadanie-stare",
        liczba_do_przetworzenia=10,
        okres=okres,
        komunikat=StatusGenerowania.KOMUNIKAT_OBLICZANIE,
    )
    StatusGenerowania.objects.filter(pk=status.pk).update(
        liczba_przetworzonych=4,
        data_rozpoczecia=timezone.now() - timedelta(seconds=wiek),
    )
    status.refresh_from_db()
    return status


def test_generowanie_przerwane_w_trakcie_jest_anulowane(
    admin_client, uczelnia, okres_2022
):
    wybierz_okres(admin_client, okres_2022)
    status = _w_polowie(uczelnia, okres_2022)

    with patch(POWOD, return_value=MARTWY):
        html = admin_client.get(
            reverse("ewaluacja_metryki:status_partial")
        ).content.decode()

    status.refresh_from_db()
    assert not status.w_trakcie
    assert status.anulowane
    assert "przerwane przed zakończeniem" in status.ostatni_komunikat
    assert "Generowanie metryk zostało anulowane" in html
    assert "przerwane przed zakończeniem" in html
    assert PRZYCISK_AKTYWNY in html
    assert PRZYCISK_ZABLOKOWANY not in html
    # ramka przestaje się odpytywać
    assert "hx-trigger" not in html


def test_generowanie_ktore_pracuje_zostaje(admin_client, uczelnia, okres_2022):
    wybierz_okres(admin_client, okres_2022)
    status = _w_polowie(uczelnia, okres_2022)

    with patch(POWOD, return_value=None):
        html = admin_client.get(
            reverse("ewaluacja_metryki:status_partial")
        ).content.decode()

    status.refresh_from_db()
    assert status.w_trakcie
    assert PRZYCISK_ZABLOKOWANY in html


def test_gotowy_wynik_zadania_rodzica_nie_chroni_przebiegu(uczelnia, okres_2022):
    """``task_id`` to zadanie, które kończy się zaraz po rozesłaniu zadań
    per autor — jego gotowy wynik nie znaczy, że przebieg się skończył."""
    _w_polowie(uczelnia, okres_2022)

    with (
        patch(POWOD, return_value=MARTWY),
        patch("celery.result.AsyncResult.ready", return_value=True),
    ):
        status = StatusGenerowania.aktualny(uczelnia=uczelnia, okres=okres_2022)

    assert status.anulowane
