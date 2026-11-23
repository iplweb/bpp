"""FD#633: przebieg modułu optymalizacji, którego zadanie w tle padło
(restart workera, ubity proces, niedziałająca usługa zadań), wisiał jako
„w trakcie” bez końca — strona statusu kręciła się w nieskończoność,
a ponowne uruchomienie przekierowywało z powrotem na nią."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa
from ewaluacja_common.przebiegi import BRAK_WORKERA, MARTWY
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from ewaluacja_optymalizacja.models import (
    OptimizationRun,
    StatusDisciplineSwapAnalysis,
    StatusOdpinaniaWszystkich,
    StatusOptymalizacjiBulk,
    StatusOptymalizacjiZOdpinaniem,
    StatusPrzegladarkaRecalc,
    StatusUnpinningAnalyzy,
)

pytestmark = pytest.mark.django_db

POWOD = "ewaluacja_common.przebiegi.powod_przerwania"
GOTOWE = "celery.result.AsyncResult.ready"
TASK_ID = "zadanie-stare"
PRZERWANE = "przerwane przed zakończeniem"

WSZYSTKIE = [
    StatusOptymalizacjiZOdpinaniem,
    StatusOptymalizacjiBulk,
    StatusUnpinningAnalyzy,
    StatusDisciplineSwapAnalysis,
    StatusPrzegladarkaRecalc,
    StatusOdpinaniaWszystkich,
]


@pytest.fixture
def martwy():
    """Strażnik uznaje każdy sprawdzany przebieg za martwy (bez połączeń
    z brokerem)."""
    with patch(POWOD, return_value=MARTWY) as mock:
        yield mock


def _trwa(status_cls, wiek=600, task_id=TASK_ID, **pola):
    """Status „w trakcie” od ``wiek`` sekund."""
    status_cls.get_or_create()
    status_cls.objects.filter(pk=1).update(
        w_trakcie=True,
        task_id=task_id,
        data_rozpoczecia=timezone.now() - timedelta(seconds=wiek),
        data_zakonczenia=None,
        ostatni_komunikat="Rozpoczęto",
        **pola,
    )
    return status_cls.objects.get(pk=1)


def _raportowana_dyscyplina(uczelnia, okres):
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    baker.make(
        LiczbaNDlaUczelni,
        uczelnia=uczelnia,
        okres=okres,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=20,
    )
    return dyscyplina


# --- model: anulowanie


@pytest.mark.parametrize("status_cls", WSZYSTKIE, ids=lambda c: c.__name__)
def test_martwy_przebieg_jest_anulowany(status_cls, martwy):
    _trwa(status_cls)

    status = status_cls.aktualny()

    assert not status.w_trakcie
    assert status.przerwany
    assert PRZERWANE in status.ostatni_komunikat
    assert status.ostatni_komunikat.startswith(status_cls.NAZWA_PRZEBIEGU)
    assert status.komunikat_przerwania_dla(TASK_ID)
    assert status.komunikat_przerwania_dla("inne-zadanie") is None


@pytest.mark.parametrize("status_cls", WSZYSTKIE, ids=lambda c: c.__name__)
def test_zywy_przebieg_zostaje(status_cls):
    _trwa(status_cls)

    with patch(POWOD, return_value=None):
        status = status_cls.aktualny()

    assert status.w_trakcie
    assert not status.przerwany


def test_swiezo_zlecony_przebieg_nie_jest_sprawdzany(martwy):
    _trwa(StatusUnpinningAnalyzy, wiek=5)

    assert StatusUnpinningAnalyzy.aktualny().w_trakcie
    martwy.assert_not_called()


def test_zadanie_z_gotowym_wynikiem_zostawiamy_widokom(martwy):
    """Zadanie skończyło pracę, tylko nikt nie zdjął flagi — to nie jest
    przebieg przerwany; sprząta go widok, jak dotąd."""
    _trwa(StatusUnpinningAnalyzy)

    with patch(GOTOWE, return_value=True):
        status = StatusUnpinningAnalyzy.aktualny()

    assert status.w_trakcie
    martwy.assert_not_called()


def test_brak_uslugi_zadan_daje_inny_komunikat():
    _trwa(StatusDisciplineSwapAnalysis)

    with patch(POWOD, return_value=BRAK_WORKERA):
        status = StatusDisciplineSwapAnalysis.aktualny()

    assert status.przerwany
    assert "usługa przetwarzania zadań w tle nie działa" in status.ostatni_komunikat
    assert "administratorowi" in status.ostatni_komunikat


def test_nowy_przebieg_zlecony_w_trakcie_sprawdzania_nie_jest_anulowany():
    """Anulowanie jest warunkowe: dotyczy tylko przebiegu, który oceniano."""
    stary = _trwa(StatusUnpinningAnalyzy)

    def zlec_nowy(*args, **kwargs):
        StatusUnpinningAnalyzy.objects.filter(pk=1).update(task_id="zadanie-nowe")
        return MARTWY

    with patch(POWOD, side_effect=zlec_nowy):
        assert stary.anuluj_jesli_martwy() is False

    nowy = StatusUnpinningAnalyzy.objects.get(pk=1)
    assert nowy.w_trakcie
    assert nowy.task_id == "zadanie-nowe"


# --- „Policz całą ewaluację”: zadanie-rodzic kończy się od razu


def test_bulk_ze_wszystkimi_wynikami_nie_jest_przerwany(uczelnia, okres_2022, martwy):
    """Wszystkie dyscypliny policzone, flagę zdejmie strona statusu —
    strażnik nie może nazwać udanego przebiegu przerwanym."""
    dyscyplina = _raportowana_dyscyplina(uczelnia, okres_2022)
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        okres=okres_2022,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )
    _trwa(StatusOptymalizacjiBulk, uczelnia=uczelnia, okres=okres_2022)

    assert StatusOptymalizacjiBulk.aktualny().w_trakcie
    martwy.assert_not_called()


def test_bulk_przerwany_oznacza_niedokonczone_dyscypliny(uczelnia, okres_2022, martwy):
    dyscyplina = _raportowana_dyscyplina(uczelnia, okres_2022)
    w_toku = baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        okres=okres_2022,
        dyscyplina_naukowa=dyscyplina,
        status="running",
    )
    _trwa(StatusOptymalizacjiBulk, uczelnia=uczelnia, okres=okres_2022)

    assert StatusOptymalizacjiBulk.aktualny().przerwany

    w_toku.refresh_from_db()
    assert w_toku.status == "failed"
    assert "Przerwane" in w_toku.notes


# --- strony statusu


@pytest.mark.parametrize(
    "status_cls,url",
    [
        (StatusOptymalizacjiZOdpinaniem, "optimize-unpin-status"),
        (StatusUnpinningAnalyzy, "unpinning-combined-status"),
        (StatusDisciplineSwapAnalysis, "discipline-swap-status"),
        (StatusOdpinaniaWszystkich, "unpin-all-sensible-status"),
    ],
    ids=lambda p: p if isinstance(p, str) else "",
)
@pytest.mark.parametrize("htmx", [False, True], ids=["strona", "htmx"])
def test_strona_statusu_pokazuje_przerwanie(
    status_cls, url, htmx, admin_client, uczelnia, martwy
):
    _trwa(status_cls)
    naglowki = {"HTTP_HX_REQUEST": "true"} if htmx else {}

    odpowiedz = admin_client.get(
        reverse(f"ewaluacja_optymalizacja:{url}", args=[TASK_ID]), **naglowki
    )

    html = odpowiedz.content.decode()
    assert odpowiedz.status_code == 200
    assert PRZERWANE in html
    assert not status_cls.objects.get(pk=1).w_trakcie


def test_strona_statusu_zywego_przebiegu_bez_zmian(admin_client, uczelnia):
    _trwa(StatusDisciplineSwapAnalysis)

    with patch(POWOD, return_value=None):
        html = admin_client.get(
            reverse("ewaluacja_optymalizacja:discipline-swap-status", args=[TASK_ID])
        ).content.decode()

    assert PRZERWANE not in html
    assert StatusDisciplineSwapAnalysis.objects.get(pk=1).w_trakcie


def test_strona_statusu_bulk_pokazuje_przerwanie(
    admin_client, uczelnia, okres_2022, martwy
):
    _raportowana_dyscyplina(uczelnia, okres_2022)
    _trwa(StatusOptymalizacjiBulk, uczelnia=uczelnia, okres=okres_2022)

    html = admin_client.get(
        reverse("ewaluacja_optymalizacja:bulk-status", args=[uczelnia.pk, TASK_ID])
    ).content.decode()

    assert PRZERWANE in html
    assert "Oczekiwanie na rozpoczęcie przetwarzania" not in html
    assert not StatusOptymalizacjiBulk.objects.get(pk=1).w_trakcie


def test_okno_przeliczania_przegladarki_pokazuje_przerwanie(
    admin_client, uczelnia, okres_2022, martwy
):
    _raportowana_dyscyplina(uczelnia, okres_2022)
    _trwa(
        StatusPrzegladarkaRecalc,
        uczelnia=uczelnia,
        okres=okres_2022,
        punkty_przed={},
    )

    html = admin_client.get(
        reverse("ewaluacja_optymalizacja:browser-recalc-status")
    ).content.decode()

    assert "Przeliczanie przerwane" in html
    assert PRZERWANE in html
    # okno przestaje się odpytywać
    assert "hx-trigger" not in html


# --- ponowne uruchomienie


def test_po_przerwaniu_mozna_uruchomic_analize_ponownie(admin_client, uczelnia, martwy):
    """Wcześniej: przekierowanie na stronę statusu martwego zadania."""
    _trwa(StatusDisciplineSwapAnalysis)

    with patch(
        "ewaluacja_optymalizacja.tasks.analyze_discipline_swap_task.delay",
        return_value=MagicMock(id="zadanie-nowe"),
    ) as delay:
        odpowiedz = admin_client.get(
            reverse("ewaluacja_optymalizacja:analyze-discipline-swap")
        )

    delay.assert_called_once()
    assert odpowiedz.status_code == 302
    assert odpowiedz.url.endswith("/zadanie-nowe/")
    # status zapisany już przy zleceniu — strażnik ma czego pilnować, gdyby
    # i to zadanie nie wystartowało
    status = StatusDisciplineSwapAnalysis.objects.get(pk=1)
    assert status.w_trakcie
    assert status.task_id == "zadanie-nowe"
