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
    # 286 = htmx przestaje odpytywać (wyzwalacz siedzi na kontenerze, którego
    # podmiana wnętrza nie usuwa)
    assert odpowiedz.status_code == (286 if htmx else 200)
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

    url = reverse("ewaluacja_optymalizacja:bulk-status", args=[uczelnia.pk, TASK_ID])
    html = admin_client.get(url).content.decode()

    assert PRZERWANE in html
    assert admin_client.get(url, HTTP_HX_REQUEST="true").status_code == 286
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


def test_strona_glowna_modulu_pokazuje_komunikat_przerwania(
    admin_client, uczelnia, martwy
):
    """Bez komunikatu link „Zobacz status…” po prostu by zniknął."""
    _trwa(StatusOptymalizacjiZOdpinaniem)

    html = admin_client.get(reverse("ewaluacja_optymalizacja:index")).content.decode()

    assert PRZERWANE in html
    assert "Zobacz status optymalizacji" not in html


# --- zadanie, które rusza już po anulowaniu


def _anulowany(status_cls, **pola):
    _trwa(status_cls, **pola)
    with patch(POWOD, return_value=BRAK_WORKERA):
        assert status_cls.aktualny().przerwany


def test_anulowana_optymalizacja_z_odpinaniem_nie_odpina(uczelnia):
    """Usługa zadań nie działała, przebieg anulowano, zadanie zostało
    w kolejce. Gdy usługa wraca, zadanie NIE może wykonać masowego odpinania,
    o którym użytkownik przeczytał, że zostało anulowane."""
    from ewaluacja_optymalizacja.tasks import optimize_and_unpin_task

    _anulowany(StatusOptymalizacjiZOdpinaniem)

    wynik = optimize_and_unpin_task.apply(args=[uczelnia.pk], task_id=TASK_ID).get()

    assert wynik["status"] == "cancelled"
    status = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)
    assert status.przerwany  # zadanie nie zajęło slotu
    assert not status.w_trakcie


def test_anulowane_przeliczanie_ewaluacji_nie_liczy(uczelnia, okres_2022):
    from ewaluacja_optymalizacja.tasks import solve_all_reported_disciplines

    _raportowana_dyscyplina(uczelnia, okres_2022)
    _anulowany(StatusOptymalizacjiBulk, uczelnia=uczelnia, okres=okres_2022)

    with patch(
        "ewaluacja_optymalizacja.tasks.optimization.solve_single_discipline_task"
    ) as podzadanie:
        wynik = solve_all_reported_disciplines.apply(
            args=[uczelnia.pk], kwargs={"okres_pk": okres_2022.pk}, task_id=TASK_ID
        ).get()

    assert wynik["status"] == "cancelled"
    podzadanie.s.assert_not_called()


def test_nowy_przebieg_po_anulowanym_dziala_normalnie(uczelnia):
    """Anulowanie dotyczy konkretnego zadania — następne (inny identyfikator)
    przechodzi przez zabezpieczenie."""
    _anulowany(StatusOptymalizacjiZOdpinaniem)

    assert not StatusOptymalizacjiZOdpinaniem.przebieg_anulowany("zadanie-nowe")
    assert StatusOptymalizacjiZOdpinaniem.przebieg_anulowany(TASK_ID)


# --- odpinanie sensownych możliwości: zadanie, które nigdy nie wystartowało

WYSLIJ = "ewaluacja_optymalizacja.tasks.unpin_all_sensible_task.apply_async"


def _wyslane(**kwargs):
    """Atrapa wysłania zadania: zwraca wynik o zleconym identyfikatorze."""
    return MagicMock(id=kwargs["task_id"])


def test_odpinanie_sensownych_zostawia_slad_juz_przy_zleceniu(admin_client, uczelnia):
    """Wcześniej status zapisywało dopiero samo zadanie — gdy nie wystartowało,
    strona postępu kręciła się bez końca i strażnik nie miał czego anulować."""
    with patch(WYSLIJ, side_effect=_wyslane) as wyslij:
        odpowiedz = admin_client.get(
            reverse("ewaluacja_optymalizacja:unpin-all-sensible")
        )

    wyslij.assert_called_once()
    status = StatusOdpinaniaWszystkich.objects.get(pk=1)
    assert status.w_trakcie
    assert status.task_id == wyslij.call_args.kwargs["task_id"]
    assert odpowiedz.url.endswith(f"/{status.task_id}/")


def test_odpinanie_sensownych_ktore_nie_wystartowalo_jest_anulowane(
    admin_client, uczelnia, martwy
):
    with patch(WYSLIJ, side_effect=_wyslane):
        url_statusu = admin_client.get(
            reverse("ewaluacja_optymalizacja:unpin-all-sensible")
        ).url
    StatusOdpinaniaWszystkich.objects.filter(pk=1).update(
        data_rozpoczecia=timezone.now() - timedelta(seconds=600)
    )

    html = admin_client.get(url_statusu).content.decode()

    assert PRZERWANE in html
    assert StatusOdpinaniaWszystkich.objects.get(pk=1).przerwany


def test_odpinanie_sensownych_w_toku_przekierowuje_na_status(admin_client, uczelnia):
    _trwa(StatusOdpinaniaWszystkich)

    with patch(POWOD, return_value=None), patch(WYSLIJ) as wyslij:
        odpowiedz = admin_client.get(
            reverse("ewaluacja_optymalizacja:unpin-all-sensible")
        )

    wyslij.assert_not_called()
    assert odpowiedz.url.endswith(f"/{TASK_ID}/")


def test_odpinanie_sensownych_po_przerwaniu_mozna_uruchomic_ponownie(
    admin_client, uczelnia, martwy
):
    _trwa(StatusOdpinaniaWszystkich)

    with patch(WYSLIJ, side_effect=_wyslane) as wyslij:
        admin_client.get(reverse("ewaluacja_optymalizacja:unpin-all-sensible"))

    wyslij.assert_called_once()
    status = StatusOdpinaniaWszystkich.objects.get(pk=1)
    assert status.w_trakcie
    assert status.task_id != TASK_ID


def test_odpinanie_sensownych_zwalnia_slot_gdy_zadanie_juz_jest(admin_client, uczelnia):
    from celery_singleton import DuplicateTaskError

    with patch(WYSLIJ, side_effect=DuplicateTaskError("już jest", "inne")):
        admin_client.get(reverse("ewaluacja_optymalizacja:unpin-all-sensible"))

    assert not StatusOdpinaniaWszystkich.objects.get(pk=1).w_trakcie


def test_anulowane_odpinanie_sensownych_nie_odpina(uczelnia):
    from ewaluacja_optymalizacja.tasks import unpin_all_sensible_task

    _anulowany(StatusOdpinaniaWszystkich)

    with patch(
        "ewaluacja_optymalizacja.tasks.unpin_all_sensible._unpin_all_sensible"
    ) as odpinanie:
        wynik = unpin_all_sensible_task.apply(args=[uczelnia.pk], task_id=TASK_ID).get()

    assert wynik["status"] == "cancelled"
    odpinanie.assert_not_called()
    assert StatusOdpinaniaWszystkich.objects.get(pk=1).przerwany


# --- blokada celery_singleton po anulowaniu


def test_anulowanie_zdejmuje_blokade_singletona_tego_zadania(martwy):
    """Bez tego ponowne uruchomienie kończyłoby się „zadanie jest już
    uruchomione” aż do wygaśnięcia blokady (godziny)."""
    from celery_singleton.backends import get_backend
    from celery_singleton.config import Config

    from django_bpp.celery_tasks import app

    config = Config(app)
    redis = get_backend(config).redis
    nasza = f"{config.key_prefix}test-fd633-nasza"
    cudza = f"{config.key_prefix}test-fd633-cudza"
    redis.set(nasza, TASK_ID, ex=60)
    redis.set(cudza, "inne-zadanie", ex=60)
    try:
        _trwa(StatusDisciplineSwapAnalysis)
        assert StatusDisciplineSwapAnalysis.aktualny().przerwany

        assert redis.get(nasza) is None
        assert redis.get(cudza) == "inne-zadanie"
    finally:
        redis.delete(nasza, cudza)
