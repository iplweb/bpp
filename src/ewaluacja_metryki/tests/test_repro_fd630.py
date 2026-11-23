"""FD#630: generowanie metryk, które nigdy nie wystartowało (nie działa
worker Celery, kolejka stoi), wisiało na „Oczekiwanie na rozpoczęcie
przetwarzania…” bez końca i blokowało przycisk „Uruchom generowanie”."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from ewaluacja_metryki import celery_worker
from ewaluacja_metryki.models import (
    DOMYSLNY_LIMIT_STARTU_SEKUNDY,
    StatusGenerowania,
)
from ewaluacja_metryki.tasks import (
    generuj_metryki_task,
    generuj_metryki_task_parallel,
)

from .conftest import wybierz_okres

pytestmark = pytest.mark.django_db

WORKER = "ewaluacja_metryki.celery_worker.czy_dziala_worker_celery"
TASK = "ewaluacja_metryki.brak_metryk.generuj_metryki_task_parallel"

PO_LIMICIE = timedelta(seconds=DOMYSLNY_LIMIT_STARTU_SEKUNDY + 60)
PRZED_LIMITEM = timedelta(seconds=DOMYSLNY_LIMIT_STARTU_SEKUNDY - 60)

OCZEKIWANIE = "Oczekiwanie na rozpoczęcie przetwarzania"
PRZYCISK_AKTYWNY = 'data-open="generowanie-modal"'
PRZYCISK_ZABLOKOWANY = "Generowanie w trakcie"


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


@pytest.fixture
def worker():
    """Żadnych prawdziwych połączeń z brokerem: sprawdzenie workera jest
    zamockowane (domyślnie „nie działa”)."""
    with patch(WORKER, return_value=False) as mock:
        yield mock


def _zlecony(uczelnia, okres, wiek, task_id="zadanie-stare"):
    """Status zleconego generowania sprzed ``wiek`` — zadanie nie ruszyło."""
    status = StatusGenerowania.get_or_create(uczelnia=uczelnia, okres=okres)
    status.rozpocznij_generowanie(
        task_id=task_id, liczba_do_przetworzenia=10, okres=okres
    )
    StatusGenerowania.objects.filter(pk=status.pk).update(
        data_rozpoczecia=timezone.now() - wiek
    )
    status.refresh_from_db()
    return status


def _status_partial(client):
    return client.get(reverse("ewaluacja_metryki:status_partial")).content.decode()


# (a) utknięty przebieg po progu → anulowany, komunikat, przycisk aktywny


def test_utkniety_przebieg_po_limicie_jest_anulowany(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    html = _status_partial(admin_client)

    status.refresh_from_db()
    assert not status.w_trakcie
    assert status.anulowane
    assert "nie rozpoczęło się w ciągu 5 min" in status.ostatni_komunikat
    assert OCZEKIWANIE not in html
    assert "Generowanie metryk zostało anulowane" in html
    assert "nie rozpoczęło się w ciągu 5 min" in html
    assert PRZYCISK_AKTYWNY in html
    assert PRZYCISK_ZABLOKOWANY not in html
    # ramka przestaje się odpytywać
    assert "hx-trigger" not in html


def test_lista_metryk_tez_anuluje_utkniety_przebieg(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    html = admin_client.get(reverse("ewaluacja_metryki:lista")).content.decode()

    assert "Generowanie metryk zostało anulowane" in html
    assert OCZEKIWANIE not in html
    assert PRZYCISK_ZABLOKOWANY not in html


def test_status_json_anuluje_utkniety_przebieg(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    dane = admin_client.get(reverse("ewaluacja_metryki:status_generowania")).json()

    assert dane["w_trakcie"] is False
    assert dane["anulowane"] is True


def test_limit_startu_z_ustawien(admin_client, uczelnia, okres_2022, worker, settings):
    settings.EWALUACJA_METRYKI_LIMIT_STARTU_SEKUNDY = 30
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, timedelta(seconds=45))

    _status_partial(admin_client)

    status.refresh_from_db()
    assert status.anulowane


# (b) przed progiem → nadal „Oczekiwanie…”


def test_przed_limitem_nadal_oczekiwanie(admin_client, uczelnia, okres_2022, worker):
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, PRZED_LIMITEM)

    html = _status_partial(admin_client)

    status.refresh_from_db()
    assert status.w_trakcie
    assert OCZEKIWANIE in html
    assert PRZYCISK_ZABLOKOWANY in html
    worker.assert_not_called()


# (c) przebieg, który ruszył, NIE jest anulowany mimo upływu czasu


def test_przebieg_z_przetworzonymi_autorami_nie_jest_anulowany(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE)
    StatusGenerowania.objects.filter(pk=status.pk).update(liczba_przetworzonych=3)

    html = _status_partial(admin_client)

    status.refresh_from_db()
    assert status.w_trakcie
    assert "Generowanie metryk w trakcie" in html
    worker.assert_not_called()


def test_przebieg_ktory_zglosil_start_nie_jest_anulowany(
    admin_client, uczelnia, okres_2022, worker
):
    """Faza „przeliczanie liczby N” może trwać dłużej niż limit startu —
    zadanie zgłasza start, zanim przetworzy pierwszego autora."""
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE)
    assert status.potwierdz_start("zadanie-stare")

    html = _status_partial(admin_client)

    status.refresh_from_db()
    assert status.w_trakcie
    assert status.liczba_przetworzonych == 0
    assert OCZEKIWANIE not in html
    assert "Przeliczanie liczby N i przygotowanie danych" in html
    assert PRZYCISK_ZABLOKOWANY in html
    worker.assert_not_called()


def test_zadanie_zglasza_start_przed_przeliczeniem_liczby_n(uczelnia, okres_2022):
    """Sygnał „zadanie ruszyło” jest w statusie już w trakcie przeliczania
    liczby N — czyli zanim pojawi się pierwszy przetworzony autor."""
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE, task_id="zadanie-1")
    widziane = {}

    def podgladnij_status(**kwargs):
        s = StatusGenerowania.objects.get(pk=status.pk)
        widziane["czeka_na_start"] = s.czeka_na_start
        widziane["anulowano"] = s.anuluj_jesli_nie_wystartowalo()

    with patch(
        "ewaluacja_metryki.tasks.oblicz_liczby_n_dla_okresu",
        side_effect=podgladnij_status,
    ):
        wynik = generuj_metryki_task.apply(
            kwargs=dict(
                uczelnia_id=uczelnia.pk,
                okres_pk=okres_2022.pk,
                tylko_zlecony_przebieg=True,
            ),
            task_id="zadanie-1",
        ).get()

    assert widziane == {"czeka_na_start": False, "anulowano": False}
    assert wynik["success"] is True


# (d) komunikat „brak workera” vs „worker jest” vs „nie wiadomo”


@pytest.mark.parametrize(
    "stan_workera,oczekiwany,nieoczekiwany",
    [
        (False, "w tle nie działa — zgłoś to administratorowi", "spróbuj"),
        (True, "w tle działa — spróbuj uruchomić generowanie ponownie", "zgłoś"),
        (None, "Nie udało się sprawdzić", "nie działa —"),
    ],
)
def test_komunikat_zalezy_od_stanu_workera(
    admin_client,
    uczelnia,
    okres_2022,
    worker,
    stan_workera,
    oczekiwany,
    nieoczekiwany,
):
    worker.return_value = stan_workera
    wybierz_okres(admin_client, okres_2022)
    _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    html = _status_partial(admin_client)

    assert oczekiwany in html
    assert nieoczekiwany not in html


def test_worker_sprawdzany_tylko_raz_na_anulowany_przebieg(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    for _ in range(3):
        _status_partial(admin_client)
    admin_client.get(reverse("ewaluacja_metryki:lista"))

    worker.assert_called_once()


def _inspect(ping):
    app = MagicMock()
    app.control.inspect.return_value.ping = ping
    return patch("django_bpp.celery_tasks.app", app)


@pytest.mark.parametrize(
    "odpowiedz,oczekiwane",
    [
        ({"celery@host": {"ok": "pong"}}, True),
        (None, False),
        ({}, False),
    ],
)
def test_sprawdzenie_workera(odpowiedz, oczekiwane):
    with _inspect(MagicMock(return_value=odpowiedz)):
        assert celery_worker.czy_dziala_worker_celery() is oczekiwane


@pytest.mark.parametrize(
    "blad", [OperationalError("broker"), ConnectionRefusedError("odmowa")]
)
def test_blad_sprawdzenia_workera_to_nie_wiadomo(blad, caplog):
    with _inspect(MagicMock(side_effect=blad)):
        assert celery_worker.czy_dziala_worker_celery() is None
    assert "Nie udało się sprawdzić" in caplog.text


def test_niedostepny_broker_nie_wywraca_strony_statusu(
    admin_client, uczelnia, okres_2022
):
    wybierz_okres(admin_client, okres_2022)
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    with _inspect(MagicMock(side_effect=OperationalError("broker"))):
        res = admin_client.get(reverse("ewaluacja_metryki:status_partial"))

    assert res.status_code == 200
    assert "Nie udało się sprawdzić" in res.content.decode()
    status.refresh_from_db()
    assert status.anulowane


# (e) spóźnione zadanie po anulowaniu nic nie psuje


@pytest.mark.parametrize("task", [generuj_metryki_task_parallel, generuj_metryki_task])
def test_spoznione_zadanie_po_anulowaniu_wychodzi_po_cichu(
    task, uczelnia, okres_2022, worker
):
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE, task_id="zadanie-stare")
    assert status.anuluj_jesli_nie_wystartowalo()
    komunikat = status.ostatni_komunikat

    with patch("ewaluacja_metryki.tasks.oblicz_liczby_n_dla_okresu") as liczba_n:
        wynik = task.apply(
            kwargs=dict(
                uczelnia_id=uczelnia.pk,
                okres_pk=okres_2022.pk,
                tylko_zlecony_przebieg=True,
            ),
            task_id="zadanie-stare",
        ).get()

    liczba_n.assert_not_called()
    assert wynik["success"] is False
    assert wynik["anulowane"] is True
    status.refresh_from_db()
    assert status.anulowane
    assert status.ostatni_komunikat == komunikat


def test_spoznione_zadanie_nie_psuje_nowego_przebiegu(uczelnia, okres_2022, worker):
    status = _zlecony(uczelnia, okres_2022, PO_LIMICIE, task_id="zadanie-stare")
    assert status.anuluj_jesli_nie_wystartowalo()
    # użytkownik uruchomił generowanie ponownie — nowe zadanie czeka w kolejce
    status.rozpocznij_generowanie(
        task_id="zadanie-nowe", liczba_do_przetworzenia=7, okres=okres_2022
    )
    przed = StatusGenerowania.objects.values().get(pk=status.pk)

    with patch("ewaluacja_metryki.tasks.oblicz_liczby_n_dla_okresu") as liczba_n:
        wynik = generuj_metryki_task_parallel.apply(
            kwargs=dict(
                uczelnia_id=uczelnia.pk,
                okres_pk=okres_2022.pk,
                tylko_zlecony_przebieg=True,
            ),
            task_id="zadanie-stare",
        ).get()

    liczba_n.assert_not_called()
    assert wynik["anulowane"] is True
    assert StatusGenerowania.objects.values().get(pk=status.pk) == przed


def test_zadanie_spoza_zlecenia_nie_jest_blokowane(uczelnia, okres_2022):
    """Strażnik: przeliczenie zlecane inną drogą (łańcuchy w optymalizacji
    ewaluacji) nie zapisuje swojego identyfikatora w statusie i ma działać
    jak dotąd."""
    with patch("ewaluacja_metryki.tasks.oblicz_liczby_n_dla_okresu") as liczba_n:
        wynik = generuj_metryki_task.apply(
            kwargs=dict(uczelnia_id=uczelnia.pk, okres_pk=okres_2022.pk),
            task_id="inne-zadanie",
        ).get()

    liczba_n.assert_called_once()
    assert wynik["success"] is True


# (f) po anulowaniu da się uruchomić generowanie ponownie


def test_po_anulowaniu_mozna_uruchomic_ponownie(
    admin_client, uczelnia, okres_2022, worker
):
    wybierz_okres(admin_client, okres_2022)
    _zlecony(uczelnia, okres_2022, PO_LIMICIE)

    with patch(TASK) as task:
        res = admin_client.post(
            reverse("ewaluacja_metryki:uruchom_generowanie"),
            {"minimalny_pk": 0.01, "nadpisz": "on"},
            HTTP_HX_REQUEST="true",
        )

    task.apply_async.assert_called_once()
    wywolanie = task.apply_async.call_args.kwargs
    assert wywolanie["kwargs"]["tylko_zlecony_przebieg"] is True
    status = StatusGenerowania.objects.get(uczelnia=uczelnia, okres=okres_2022)
    assert status.w_trakcie
    assert status.czeka_na_start
    # identyfikator zadania jest w statusie, zanim zadanie trafi do kolejki
    assert status.task_id == wywolanie["task_id"] != "zadanie-stare"
    html = res.content.decode()
    assert OCZEKIWANIE in html
    assert PRZYCISK_ZABLOKOWANY in html


def test_blad_zlecenia_nie_zostawia_statusu_w_trakcie(
    admin_client, uczelnia, okres_2022
):
    wybierz_okres(admin_client, okres_2022)

    with patch(TASK) as task:
        task.apply_async.side_effect = OperationalError("broker")
        with pytest.raises(OperationalError):
            admin_client.post(
                reverse("ewaluacja_metryki:uruchom_generowanie"),
                {"minimalny_pk": 0.01, "nadpisz": "on"},
            )

    status = StatusGenerowania.objects.get(uczelnia=uczelnia, okres=okres_2022)
    assert status.anulowane
    assert "Nie udało się zlecić" in status.ostatni_komunikat


# metryki jednostek / wydziałów


@pytest.fixture
def jednostka(uczelnia):
    return baker.make(Jednostka, nazwa="Klinika Testowa", uczelnia=uczelnia)


def test_metryki_jednostek_pokazuja_anulowanie_i_nie_zlecaja_w_kolko(
    admin_client, jednostka, okres_2026, worker
):
    """Strona metryk jednostek sama zleca przeliczenie w okresie bez metryk.
    Gdy zadanie nie ruszy, kolejne wejścia mają pokazać powód, a nie zlecać
    następne zadania donikąd."""
    wybierz_okres(admin_client, okres_2026)
    _zlecony(jednostka.uczelnia, okres_2026, PO_LIMICIE)
    url = reverse("ewaluacja_metryki:metryki_jednostek")

    with patch(TASK) as task:
        html = admin_client.get(url).content.decode()
        admin_client.get(url)

    task.apply_async.assert_not_called()
    assert "są właśnie przeliczane" not in html
    assert "zostało anulowane" in html
    assert "w tle nie działa — zgłoś to administratorowi" in html
    worker.assert_called_once()
