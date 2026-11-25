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
BROADCAST = "django_bpp.celery_tasks.app.control.broadcast"
KOLEJKA = "ewaluacja_common.przebiegi._czeka_w_kolejce"
STAN = "ewaluacja_common.przebiegi.stan_zadan_w_celery"


def _workery(*zadania_workerow):
    """Atrapa odpowiedzi na komendę ``bpp_zadania_workera``: po jednym
    workerze na argument, każdy z listą par ``[id, nazwa]``."""
    return patch(
        BROADCAST,
        return_value=[
            {f"w{nr}": [list(para) for para in zadania]}
            for nr, zadania in enumerate(zadania_workerow)
        ],
    )


def test_zaden_worker_nie_odpowiada():
    with _workery():
        assert stan_zadan_w_celery(NAZWY, "t1") == BRAK_WORKERA


def test_worker_ma_zadanie_przebiegu():
    with _workery([("inne-id", "moje.podzadanie")]), patch(KOLEJKA) as kolejka:
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE
    # żywy przebieg widać u workera — kolejki (duże wiadomości) nie czytamy
    kolejka.assert_not_called()


def test_worker_ma_zadanie_o_tym_task_id_pod_inna_nazwa():
    with _workery([("t1", "obce.zadanie")]), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_zadanie_ma_drugi_z_workerow():
    with _workery([], [("x", "moje.zadanie")]), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_zadanie_czeka_w_kolejce():
    with _workery([]), patch(KOLEJKA, return_value=True):
        assert stan_zadan_w_celery(NAZWY, "t1") == ZYJE


def test_nikt_nie_pracuje_nad_przebiegiem():
    with _workery([("obce", "obce.zadanie")]), patch(KOLEJKA, return_value=False):
        assert stan_zadan_w_celery(NAZWY, "t1") == MARTWY


def test_kolejki_nie_da_sie_przejrzec():
    with _workery([]), patch(KOLEJKA, return_value=None):
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO


def test_worker_bez_komendy_straznika_nie_jest_dowodem():
    """Worker starszej wersji odpowiada błędem „nieznana komenda” — to nie
    znaczy, że nie ma zadania."""
    odpowiedz = [{"w0": {"error": "KeyError('bpp_zadania_workera')"}}]
    with patch(BROADCAST, return_value=odpowiedz), patch(KOLEJKA) as kolejka:
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO
    kolejka.assert_not_called()


def test_broker_niedostepny():
    with patch(BROADCAST, side_effect=OperationalError("brak brokera")):
        assert stan_zadan_w_celery(NAZWY, "t1") == NIE_WIADOMO


def test_komenda_workera_zwraca_same_identyfikatory_i_nazwy():
    """Bez argumentów zadań: zadania-porcje analiz niosą megabajty danych,
    przez które odpowiedź ``inspect().active()`` nie mieściła się w limicie."""
    from celery.worker import state as stan_workera
    from celery.worker.request import Request

    from django_bpp.celery_tasks import bpp_zadania_workera

    aktywne = MagicMock(id="a1", args=["x" * 1000])
    aktywne.name = "moje.zadanie"
    zaplanowane = MagicMock(spec=Request, id="z1")
    zaplanowane.name = "moje.podzadanie"
    state = MagicMock()
    state.tset.side_effect = lambda zbior: zbior
    state.consumer.timer.schedule.queue = [
        MagicMock(entry=MagicMock(args=[zaplanowane])),
        MagicMock(entry=MagicMock(args=[])),  # wpis timera inny niż zadanie
    ]

    with patch.object(stan_workera, "reserved_requests", {aktywne}):
        wynik = bpp_zadania_workera(state)

    assert sorted(wynik) == [["a1", "moje.zadanie"], ["z1", "moje.podzadanie"]]


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


def test_odczyty_odlegle_w_czasie_nie_potwierdzaja_stanu(db):
    """Dwa pojedyncze odczyty „martwy” w odstępie godziny (nikt nie patrzył
    na stronę) to nie dowód, że przez godzinę nikt nie pracował."""
    with patch(STAN, return_value=MARTWY):
        powod_przerwania("k", NAZWY, "t1", _dawno())
        _postarz_odczyt("k", 3600)
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) is None
        # dopiero kolejny, bliski odczyt potwierdza
        _postarz_odczyt("k", przebiegi.POTWIERDZENIE_MARTWEGO_SEKUNDY + 1)
        assert powod_przerwania("k", NAZWY, "t1", _dawno()) == MARTWY


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
        # przed limitem przebiegu — nigdy
        assert powod_przerwania("k", NAZWY, "t1", _dawno(600), 7200) is None
        _postarz_odczyt("k", 100)
        assert powod_przerwania("k", NAZWY, "t1", _dawno(600), 7200) is None
        # po limicie — ale nie po pojedynczym odczycie
        assert powod_przerwania("inny", NAZWY, "t1", _dawno(8000), 7200) is None
        _postarz_odczyt("inny", przebiegi.POTWIERDZENIE_MARTWEGO_SEKUNDY + 1)
        assert (
            powod_przerwania("inny", NAZWY, "t1", _dawno(8000), 7200)
            == PRZEKROCZONY_LIMIT
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
