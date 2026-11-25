"""Okres bez policzonych metryk na „Metrykach jednostek/wydziałów”:
komunikat albo automatyczne przeliczenie zamiast 404."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from bpp.models.profile import BppUser
from ewaluacja_metryki.models import StatusGenerowania

from .conftest import wybierz_okres

TASK = "ewaluacja_metryki.brak_metryk.generuj_metryki_task_parallel"


@pytest.fixture
def jednostka(db):
    return baker.make(Jednostka, nazwa="Klinika Testowa", uczelnia=baker.make(Uczelnia))


def _zaloguj(client, **kwargs):
    user = baker.make(BppUser, **kwargs)
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_raport_w_okresie_bez_metryk_przekierowuje_i_przelicza(
    client,
    jednostka,
    okres_2022,
    okres_2026,
):
    _zaloguj(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2026)

    with patch(TASK) as task:
        task.apply_async.return_value = MagicMock(id="zadanie-1")
        url = reverse("ewaluacja_metryki:metryki_jednostki", args=[jednostka.pk])
        res = client.get(url, follow=True)

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "nie ma metryk ewaluacyjnych w okresie" in tresc
    assert "uruchomiono ich przeliczenie z ustawieniami domyślnymi" in tresc
    task.apply_async.assert_called_once()
    assert task.apply_async.call_args.kwargs["kwargs"]["okres_pk"] == okres_2026.pk
    assert StatusGenerowania.objects.get(okres=okres_2026).w_trakcie


@pytest.mark.django_db
def test_przeliczanie_w_trakcie_nie_startuje_drugi_raz(
    client,
    jednostka,
    okres_2026,
):
    _zaloguj(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2026)
    url = reverse("ewaluacja_metryki:metryki_jednostek")

    with patch(TASK) as task:
        task.apply_async.return_value = MagicMock(id="zadanie-1")
        client.get(url)
        res = client.get(url)

    task.apply_async.assert_called_once()
    assert "są właśnie przeliczane" in res.content.decode()


@pytest.mark.django_db
def test_zakonczone_przeliczenie_bez_wynikow_nie_startuje_ponownie(
    client,
    jednostka,
    okres_2026,
):
    status = StatusGenerowania.get_or_create(
        uczelnia=jednostka.uczelnia, okres=okres_2026
    )
    status.data_zakonczenia = timezone.now()
    status.save()
    _zaloguj(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2026)

    with patch(TASK) as task:
        res = client.get(reverse("ewaluacja_metryki:metryki_jednostek"))

    task.apply_async.assert_not_called()
    assert "nie dało żadnych metryk" in res.content.decode()


@pytest.mark.django_db
def test_bez_uprawnien_do_przeliczania_tylko_komunikat(
    client,
    jednostka,
    okres_2026,
):
    user = _zaloguj(client)
    user.jednostki_metryk.add(jednostka)
    wybierz_okres(client, okres_2026)

    with patch(TASK) as task:
        res = client.get(reverse("ewaluacja_metryki:metryki_jednostek"))

    assert res.status_code == 200
    task.apply_async.assert_not_called()
    assert "nie zostały jeszcze policzone" in res.content.decode()
