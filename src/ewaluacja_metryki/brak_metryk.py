"""Okres ewaluacji bez policzonych metryk — zamiast 404 komunikat albo
automatyczne przeliczenie z ustawieniami domyślnymi.

Przełączenie paska okresu na okres, w którym metryk jeszcze nie policzono
(np. nowy 2026–2030), kończyło się 404 na stronach „Metryki jednostek”
i „Metryki wydziałów”. Teraz:

- użytkownik, który może przeliczać metryki, przy pierwszym wejściu
  uruchamia przeliczenie z ustawieniami domyślnymi (te same co przycisk
  „Generuj” bez zmienionych parametrów),
- pozostali dostają komunikat, że metryk w tym okresie jeszcze nie ma.

Przeliczenie startuje automatycznie TYLKO, gdy dla tej uczelni i okresu nigdy
go nie kończono (``StatusGenerowania.data_zakonczenia`` puste) — jeśli
zakończone przeliczenie nie dało metryk (np. brak liczby N), nie odpalamy go
w kółko przy każdym odświeżeniu strony.
"""

import logging
from dataclasses import dataclass

from celery import uuid as celery_uuid

from bpp.permissions import moze_wprowadzac_dane
from ewaluacja_common.models import Rodzaj_Autora

from .models import MetrykaAutora, StatusGenerowania
from .tasks import generuj_metryki_task_parallel
from .uczelnia_scope import scope_metryki

logger = logging.getLogger(__name__)


def moze_przeliczac_metryki(user) -> bool:
    """Te same warunki co ``UruchomGenerowanieView``: pełne uprawnienia
    ewaluacji (``ma_pelne_uprawnienia_ewaluacji`` = ``moze_wprowadzac_dane``)
    i konto personelu."""
    return bool(user.is_staff and moze_wprowadzac_dane(user))


def uruchom_generowanie_metryk(
    uczelnia, okres, *, minimalny_pk=0.01, nadpisz=True, rodzaje_autora=None
):
    """Oznacza status jako „w trakcie” i zleca przeliczenie metryk (zadanie
    Celery). Zwraca ``(status, wynik_zadania)``."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    if not rodzaje_autora:
        # Domyślnie wszystkie rodzaje autorów, dla których liczymy sloty.
        rodzaje_autora = list(
            Rodzaj_Autora.objects.filter(licz_sloty=True).values_list(
                "skrot", flat=True
            )
        )

    udzialy = IloscUdzialowDlaAutoraZaCalosc.objects.filter(okres=okres)
    if uczelnia:
        udzialy = udzialy.filter(uczelnia=uczelnia)

    # Status „w trakcie” — razem z identyfikatorem zadania — zapisujemy
    # PRZED wysłaniem zadania do kolejki: zadanie na starcie porównuje swój
    # identyfikator z tym w statusie (i wychodzi, jeśli przebieg anulowano
    # albo zastąpiono), więc nie może wyprzedzić tego zapisu.
    task_id = celery_uuid()
    status = StatusGenerowania.get_or_create(uczelnia=uczelnia, okres=okres)
    status.rozpocznij_generowanie(
        task_id=task_id,
        liczba_do_przetworzenia=udzialy.count(),
        okres=okres,
    )

    try:
        wynik = generuj_metryki_task_parallel.apply_async(
            kwargs=dict(
                rok_min=okres.rok_od,
                rok_max=okres.rok_do,
                okres_pk=okres.pk,
                minimalny_pk=minimalny_pk,
                nadpisz=nadpisz,
                przelicz_liczbe_n=True,  # zawsze przeliczaj liczbę N
                rodzaje_autora=rodzaje_autora,
                uczelnia_id=uczelnia.pk if uczelnia else None,
                tylko_zlecony_przebieg=True,
            ),
            task_id=task_id,
        )
    except Exception:
        # Zadania nie udało się nawet wysłać (np. broker niedostępny):
        # nie zostawiamy statusu „w trakcie” do upływu limitu startu.
        logger.exception("Nie udało się zlecić generowania metryk")
        status.oznacz_anulowane(
            "Nie udało się zlecić generowania metryk: usługa przetwarzania "
            "zadań w tle jest niedostępna. Zgłoś to administratorowi systemu."
        )
        raise
    # W trybie „eager” (testy, dev bez workera) zadanie wykonało się już
    # w tym wywołaniu i zmieniło status.
    status.refresh_from_db()
    return status, wynik


@dataclass
class StanMetrykOkresu:
    okres: object
    ma_metryki: bool
    status: StatusGenerowania | None = None
    uruchomiono_teraz: bool = False
    moze_przeliczac: bool = False

    @property
    def w_trakcie(self) -> bool:
        return bool(self.status and self.status.w_trakcie)

    @property
    def anulowane(self) -> bool:
        """Ostatnie przeliczenie anulowano, bo nie wystartowało w czasie."""
        return bool(self.status and self.status.anulowane)

    @property
    def przeliczone_bez_wynikow(self) -> bool:
        """Przeliczenie się zakończyło, a metryk dalej brak."""
        return bool(
            not self.ma_metryki
            and self.status
            and not self.status.w_trakcie
            and self.status.data_zakonczenia
        )


def stan_metryk_okresu(request, uczelnia, okres, *, uruchamiaj=True):
    """Czy w okresie są metryki; jeśli nie — w razie potrzeby (i uprawnień)
    uruchamia przeliczenie z ustawieniami domyślnymi."""
    if okres is None:
        return StanMetrykOkresu(okres=None, ma_metryki=False)

    ma_metryki = scope_metryki(MetrykaAutora.objects.all(), uczelnia, okres).exists()
    if ma_metryki:
        return StanMetrykOkresu(okres=okres, ma_metryki=True)

    moze = moze_przeliczac_metryki(request.user)
    status = StatusGenerowania.aktualny(uczelnia=uczelnia, okres=okres)
    uruchomiono = False
    # Anulowanego przebiegu (zadanie nie wystartowało, np. nie działa worker)
    # nie wznawiamy automatycznie — inaczej każde wejście na stronę zlecałoby
    # kolejne zadanie donikąd, a użytkownik nie zobaczyłby powodu.
    if (
        uruchamiaj
        and moze
        and not status.w_trakcie
        and status.data_zakonczenia is None
        and not status.anulowane
    ):
        status, _ = uruchom_generowanie_metryk(uczelnia, okres)
        uruchomiono = True

    return StanMetrykOkresu(
        okres=okres,
        ma_metryki=False,
        status=status,
        uruchomiono_teraz=uruchomiono,
        moze_przeliczac=moze,
    )
