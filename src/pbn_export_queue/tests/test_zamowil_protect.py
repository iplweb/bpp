"""Konta z wpisami kolejki PBN nie da się usunąć (``zamowil`` = PROTECT).

Kto zlecił wysyłkę/wycofanie w PBN jest śladem audytu — konto się
dezaktywuje zamiast kasować. Admin pokazuje czytelną stronę „chronione
obiekty", a nie błąd 500.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue

pytestmark = pytest.mark.django_db


def _konto_z_wpisem():
    konto = baker.make(get_user_model())
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=baker.make(Wydawnictwo_Ciagle),
        zamowil=konto,
    )
    return konto


def test_konta_z_wpisem_kolejki_nie_da_sie_usunac():
    konto = _konto_z_wpisem()
    with pytest.raises(ProtectedError):
        konto.delete()


def test_admin_pokazuje_komunikat_zamiast_500(admin_client):
    konto = _konto_z_wpisem()
    model = get_user_model()._meta
    url = reverse(f"admin:{model.app_label}_{model.model_name}_delete", args=[konto.pk])

    res = admin_client.post(url, {"post": "yes"})

    assert res.status_code == 200
    assert get_user_model().objects.filter(pk=konto.pk).exists()
    assert "Kolejka eksportu do PBN" in res.content.decode()
