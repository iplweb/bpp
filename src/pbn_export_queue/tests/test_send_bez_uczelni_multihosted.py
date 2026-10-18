"""Wpis kolejki bez uczelni w instalacji wielouczelnianej (Rollbar #5359).

Stare wpisy (np. ze scalania autorów) mają ``uczelnia=None``. Przy >1
uczelni nie da się bezpiecznie ustalić, do którego PBN je wysłać —
wpis ma dostać czytelny komunikat, a nie surowy ``MultipleObjectsReturned``
z tracebackiem i zgłoszeniem w Rollbarze.
"""

from unittest import mock

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu, SendStatus


@pytest.mark.django_db
def test_send_to_pbn_bez_uczelni_przy_wielu_uczelniach(
    wydawnictwo_ciagle, admin_user, uczelnia
):
    baker.make(Uczelnia, skrot="U2")
    assert Uczelnia.objects.count() > 1

    wpis = PBN_Export_Queue.objects.create(
        rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    with (
        mock.patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as send_mock,
        mock.patch("rollbar.report_exc_info") as rollbar_mock,
    ):
        wynik = wpis.send_to_pbn()

    assert wynik == SendStatus.FINISHED_ERROR
    send_mock.assert_not_called()
    rollbar_mock.assert_not_called()
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie is False
    assert wpis.rodzaj_bledu == RodzajBledu.TECHNICZNY
    assert "nie ma przypisanej uczelni" in wpis.komunikat
    assert "MultipleObjectsReturned" not in wpis.komunikat


@pytest.mark.django_db
def test_send_to_pbn_bez_uczelni_przy_jednej_uczelni_dziala_jak_dawniej(
    wydawnictwo_ciagle, admin_user, uczelnia
):
    """Single-install: brak uczelni na wpisie nie jest problemem —
    warstwa niżej bierze jedyną uczelnię."""
    assert Uczelnia.objects.count() == 1
    wpis = PBN_Export_Queue.objects.create(
        rekord_do_wysylki=wydawnictwo_ciagle, zamowil=admin_user
    )

    with (
        mock.patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as send_mock,
        mock.patch.object(
            PBN_Export_Queue,
            "_handle_successful_send",
            return_value=SendStatus.FINISHED_OKAY,
        ),
    ):
        send_mock.return_value = (mock.MagicMock(), [])
        assert wpis.send_to_pbn() == SendStatus.FINISHED_OKAY

    send_mock.assert_called_once()
