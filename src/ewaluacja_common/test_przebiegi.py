"""FD#633: strażnik przebiegów w tle — rozpoznawanie, czy Celery jeszcze
pracuje nad przebiegiem, i decyzja o anulowaniu."""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from kombu.exceptions import OperationalError

from ewaluacja_common import przebiegi
from ewaluacja_common.models import OdczytPrzebiegu
from ewaluacja_common.przebiegi import (
    BRAK_WORKERA,
    MARTWY,
    NIE_WIADOMO,
    PRZEKROCZONY_LIMIT,
    ZYJE,
    powod_przerwania,
    stan_zadan_w_celery,
)

NAZWY = ("moje.zadanie", "moje.podzadanie")
INSPECT = "django_bpp.celery_tasks.app.control.inspect"
KOLEJKA = "ewaluacja_common.przebiegi._czeka_w_kolejce"
STAN = "ewaluacja_common.przebiegi.stan_zadan_w_celery"


def _inspect(active, reserved=None, scheduled=None):
    """Atrapa ``app.control.inspect(...)``: jeden worker, podane zadania."""
    inspekcja = MagicMock()
    inspekcja.active.return_value = active
    inspekcja.reserved.return_value = {"w1": []} if reserved is None else reserved
    inspekcja.scheduled.return_value = {"w1": []} if scheduled is None else scheduled
    return MagicMock(return_value=inspekcja)


def test_zaden_worker_nie_odpowiada():
    with patch(INSPECT, _inspect(active=None)):
        assert stan_zadan_w_celery(NAZWY, "t1") == BRAK_WORKERA


def test_worker_wykonuje_zadanie_przebiegu():
    aktywne = {"w1": [{"id": "inne-id", "name": "moje.podzadanie"}]}
    with patch(INSPECT, _inspect(aktywne)), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_worker_ma_zadanie_o_tym_task_id_pod_inna_nazwa():
    aktywne = {"w1": [{"id": "t1", "name": "obce.zadanie"}]}
    with patch(INSPECT, _inspect(aktywne)), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_zadanie_zaplanowane_na_pozniej_liczy_sie_jako_zywe():
    zaplanowane = {"w1": [{"eta": "x", "request": {"id": "z", "name": "moje.zadanie"}}]}
    with (
        patch(INSPECT, _inspect({"w1": []}, scheduled=zaplanowane)),
        patch(KOLEJKA, return_value=False),
    ):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_zadanie_czeka_w_kolejce():
    with patch(INSPECT, _inspect({"w1": []})), patch(KOLEJKA, return_value=True):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_nikt_nie_pracuje_nad_przebiegiem():
    aktywne = {"w1": [{"id": "obce", "name": "obce.zadanie"}]}
    with patch(INSPECT, _inspect(aktywne)), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == MARTWY


def test_kolejki_nie_da_sie_przejrzec():
    with patch(INSPECT, _inspect({"w1": []})), patch(KOLEJKA, return_value=None):
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO


def test_worker_nie_zdazyl_odpowiedziec_na_kolejne_pytanie():
    """Brak odpowiedzi na ``reserved`` to nie dowód, że zadania nie ma."""
    with (
        patch(INSPECT, _inspect({"w1": [], "w2": []}, reserved={"w1": []})),
        patch(KOLEJKA, return_value=False),
    ):
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO


def test_broker_niedostepny():
    with patch(INSPECT, side_effect=OperationalError("brak brokera")):
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO


def test_zadanie_wyslane_do_brokera_widac_w_kolejce():
    """Prawdziwy broker (Redis z testów): zadanie, którego nie podjął żaden
    worker, leży w kolejce — rozpoznajemy je po nazwie i po ``task_id``."""
    from django_bpp.celery_tasks import app

    nazwa = f"test.przebiegi.{uuid.uuid4().hex}"
    wynik = app.send_task(nazwa)
    try:
        assert przebiegi._czeka_w_kolejce(app, frozenset([nazwa]), "inne") is True
        assert przebiegi._czeka_w_kolejce(app, frozenset(), wynik.id) is True
        assert przebiegi._czeka_w_kolejce(app, frozenset(NAZWY), "inne") is False
    finally:
        with app.connection_for_read() as conn:
            klient = conn.default_channel.client
            for surowe in klient.lrange(app.conf.task_default_queue, 0, -1):
                if nazwa.encode() in surowe:
                    klient.lrem(app.conf.task_default_queue, 0, surowe)


# --- decyzja o anulowaniu


def _dawno(sekundy=3600):
    return timezone.now() - timedelta(seconds=sekundy)


def _postarz_odczyt(klucz, sekundy):
    """Udaj, że poprzedni odczyt (i początek stanu) był ``sekundy`` temu."""
    odczyt = OdczytPrzebiegu.objects.get(klucz=klucz)
    przesuniecie = timedelta(seconds=sekundy)
    odczyt.od -= przesuniecie
    odczyt.sprawdzono -= przesuniecie
    odczyt.save()


def test_swiezy_przebieg_nie_jest_sprawdzany(db):
    with patch(STAN) as stan:
        assert powod_przerwania("k", NAZWY, "t1", timezone.now()) is None
    stan.assert_not_called()


def test_pojedynczy_odczyt_martwego_nie_anuluje(db):
    with patch(STAN, return_value=MARTWY):
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) is None


def test_martwy_potwierdzony_w_czasie_anuluje(db):
    with patch(STAN, return_value=MARTWY):
        powod_przerwania("k", NAZWY, "t1", _dawno())
        _postarz_odczyt("k", przebiegi.POTWIERDZENIE_MARTWEGO_SEKUNDY + 1)
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) == MARTWY


def test_kolejne_odpytania_nie_pytaja_celery_za_kazdym_razem(db):
    with patch(STAN, return_value=MARTWY) as stan:
        powod_przerwania("k", NAZWY, "t1", _dawno())
        powod_przerwania("k", NAZWY, "t1", _dawno())
    assert stan.call_count == 1


def test_ozywienie_zeruje_licznik(db):
    with patch(STAN, return_value=MARTWY):
        powod_przerwania("k", NAZWY, "t1", _dawno())
    _postarz_odczyt("k", przebiegi.POTWIERDZENIE_MARTWEGO_SEKUNDY + 1)
    with patch(STAN, return_value=ZYJE):
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) is None
    _postarz_odczyt("k", przebiegi.ODSTEP_SPRAWDZEN_SEKUNDY + 1)
    with patch(STAN, return_value=MARTWY):
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) is None


def test_odczyt_innego_przebiegu_sie_nie_liczy(db):
    with patch(STAN, return_value=MARTWY):
        powod_przerwania("k", NAZWY, "stary", _dawno())
        _postarz_odczyt("k", przebiegi.POTWIERDZENIE_MARTWEGO_SEKUNDY + 1)
        assert powod_przerwania("k", NAZWY, "nowy", _dawno()) is None


def test_brak_workera_anuluje_dopiero_po_limicie(db, settings):
    settings.PRZEBIEGI_LIMIT_BEZ_WORKERA_SEKUNDY = 120
    with patch(STAN, return_value=BRAK_WORKERA):
        powod_przerwania("k", NAZWY, "t1", _dawno())
        _postarz_odczyt("k", 60)
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) is None
        _postarz_odczyt("k", 61)
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) == BRAK_WORKERA


def test_stan_nieznany_anuluje_tylko_po_twardym_limicie(db):
    with patch(STAN, return_value=NIE_WIADOMO):
        assert powod_przerwania("k", NAZWY, "t1", _dawno(600)) is None
        _postarz_odczyt("k", 3600)
        assert powod_przerwania("k", NAZWY, "t1", _dawno(600), 7200) is None
        _postarz_odczyt("k", 3600)
        assert (
            powod_przerwania("k", NAZWY, "t1", _dawno(8000), 7200) == PRZEKROCZONY_LIMIT
        )


# --- konfiguracja statusów


def _pilnowane_statusy():
    from ewaluacja_metryki.models import StatusGenerowania
    from ewaluacja_optymalizacja import models

    return [
        StatusGenerowania,
        models.StatusOptymalizacjiZOdpinaniem,
        models.StatusOptymalizacjiBulk,
        models.StatusUnpinningAnalyzy,
        models.StatusDisciplineSwapAnalysis,
        models.StatusPrzegladarkaRecalc,
        models.StatusOdpinaniaWszystkich,
    ]


@pytest.mark.parametrize("status_cls", _pilnowane_statusy(), ids=lambda c: c.__name__)
def test_zadania_przebiegu_to_zarejestrowane_zadania_celery(status_cls):
    """Literówka w nazwie zadania = strażnik uzna żywy przebieg za martwy."""
    import ewaluacja_metryki.tasks  # noqa: F401
    import ewaluacja_optymalizacja.tasks  # noqa: F401
    from django_bpp.celery_tasks import app

    assert status_cls.ZADANIA_PRZEBIEGU
    nieznane = [n for n in status_cls.ZADANIA_PRZEBIEGU if n not in app.tasks]
    assert not nieznane
