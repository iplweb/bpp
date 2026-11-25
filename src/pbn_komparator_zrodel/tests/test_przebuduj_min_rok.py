"""Formularz przebudowy porównania źródeł: pole „Minimalny rok” (FD#514)."""

from unittest import mock

import pytest

URL = "/komparator-zrodel-pbn/przebuduj/"


@pytest.fixture
def uruchomienie(db):
    """Dane PBN „świeże”, zadanie Celery podmienione atrapą."""
    with (
        mock.patch(
            "pbn_komparator_zrodel.views.task_views.is_pbn_journals_data_fresh",
            return_value=(True, "", None),
        ),
        mock.patch("pbn_komparator_zrodel.tasks.porownaj_zrodla_task.delay") as delay,
    ):
        delay.return_value.id = "zadanie-1"
        yield delay


def test_puste_pole_minimalny_rok_nie_daje_bledu(admin_client, uruchomienie):
    """Puste pole (dawniej błąd serwera) = domyślny rok 2022."""
    response = admin_client.post(URL, {"min_rok": "", "clear_existing": "on"})

    assert response.status_code == 302
    assert "zadanie-1" in response["Location"]
    uruchomienie.assert_called_once_with(min_rok=2022, clear_existing=True)


@pytest.mark.parametrize("wartosc", ["abc", "1500", "20222"])
def test_zly_minimalny_rok_komunikat_zamiast_bledu(admin_client, uruchomienie, wartosc):
    response = admin_client.post(URL, {"min_rok": wartosc}, follow=True)

    assert response.status_code == 200
    uruchomienie.assert_not_called()
    assert "Minimalny rok" in response.content.decode()
    assert any("Nie uruchomiono" in str(m) for m in response.context["messages"])


def test_podany_rok_trafia_do_zadania(admin_client, uruchomienie):
    """Strażnik: poprawny rok i odznaczone czyszczenie działają jak dotąd."""
    admin_client.post(URL, {"min_rok": "2026"})

    uruchomienie.assert_called_once_with(min_rok=2026, clear_existing=False)
