"""Automatyczne przeliczenia danych po aktualizacji BPP.

Gdy zmienia się sposób liczenia czegoś, co BPP przechowuje w bazie (np.
punktacja dyscyplin i sloty, FD#618), podbijamy wersję danego przeliczenia
w :data:`PRZELICZENIA`. Worker Celery po starcie (sygnał ``worker_ready``,
patrz ``django_bpp/celery_tasks.py``) zleca zadanie
``bpp.tasks.zlec_zalegle_przeliczenia``, które porównuje wersje z kodu
z zapisanymi w tabeli :class:`bpp.models.Wersja_Przeliczenia` i dla każdego
zaległego przeliczenia oznacza rekordy do przeliczenia w kolejce denorm.

Samo przeliczanie robi istniejąca kolejka denorm (``denorm-queue`` + worker
Celery, kolejka ``denorm``): rekordy liczone są partiami w tle, równolegle na
wszystkich procesach workera, każdy rekord we własnej transakcji; błąd jednego
rekordu jest logowany z tracebackiem, a jego znacznik zostaje do ponowienia.
Znaczniki są w bazie, więc przerwanie (restart, wdrożenie) niczego nie gubi.

Dlaczego start workera, a nie migracja: w czasie migracji mogą jeszcze działać
workery ze STAREJ wersji obrazu. Znaczniki dodane przez migrację mogłyby
zostać przeliczone starym kodem i skasowane. Nowy worker startuje dopiero po
zatrzymaniu starego, więc przeliczenie zawsze liczy nowy kod.

Oznaczenie rekordów i zapis nowej wersji idą w jednej transakcji, pod blokadą
wiersza wersji — kilka workerów startujących naraz zleci przeliczenie raz.
Błąd wycofuje całość; kolejny start workera spróbuje ponownie.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ROZMIAR_PARTII = 2000


@dataclass(frozen=True)
class Przeliczenie:
    nazwa: str
    #: Podbij, gdy zmienia się algorytm — po wdrożeniu BPP przeliczy dane.
    wersja: int
    #: Funkcja bez argumentów; oznacza rekordy do przeliczenia, zwraca ich liczbę.
    oznacz: Callable[[], int]
    opis: str = ""


def oznacz_do_przeliczenia_w_denorm(model, pole, qs=None):
    """Dodaje znaczniki denorm (``DirtyInstance``) dla pola ``pole`` rekordów
    ``qs`` (domyślnie wszystkich) modelu ``model``. Kolejka denorm przeliczy
    tylko to pole (``save(update_fields=[pole])``), bez reszty rekordu.

    Istniejące znaczniki są pomijane (unikalny indeks, ``ignore_conflicts``).
    Zwraca liczbę oznaczonych rekordów."""
    from denorm.models import DirtyInstance

    if qs is None:
        qs = model.objects.all()
    content_type = ContentType.objects.get_for_model(model)
    pks = list(qs.order_by().values_list("pk", flat=True).distinct())

    for start in range(0, len(pks), ROZMIAR_PARTII):
        DirtyInstance.objects.bulk_create(
            [
                DirtyInstance(content_type=content_type, object_id=pk, func_name=pole)
                for pk in pks[start : start + ROZMIAR_PARTII]
            ],
            ignore_conflicts=True,
        )
    return len(pks)


def oznacz_punktacje_dyscyplin():
    """Punktacja dyscyplin i sloty (pole ``cached_punkty_dyscyplin`` oraz
    tabele ``bpp_cache_punktacja_*``) — rekordy, które mają choć jednego
    autora z dyscypliną (tylko takie mają punktację dyscyplin)."""
    from bpp.models import Patent, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    razem = 0
    for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent):
        qs = model.objects.filter(autorzy_set__dyscyplina_naukowa__isnull=False)
        n = oznacz_do_przeliczenia_w_denorm(model, "cached_punkty_dyscyplin", qs)
        logger.info(
            "Przeliczenie punktacji dyscyplin: oznaczono %s rekordów %s",
            n,
            model.__name__,
        )
        razem += n
    return razem


#: Rejestr przeliczeń. Historia wersji ``punktacja_dyscyplin``:
#:   1 — √(k/m) i k/m z dokładnością do 4 miejsc (§ 13 ust. 6) i minimum 10%
#:       także dla slotów (§ 16 ust. 2), FD#618/FD#610, PR #1099.
PRZELICZENIA = (
    Przeliczenie(
        nazwa="punktacja_dyscyplin",
        wersja=1,
        oznacz=oznacz_punktacje_dyscyplin,
        opis="punktacja dyscyplin i sloty prac",
    ),
)


def zlec_przeliczenie(przeliczenie):
    """Zleca jedno przeliczenie, jeśli wersja w bazie jest niższa niż w kodzie.

    Zwraca liczbę oznaczonych rekordów albo ``None``, gdy nie było potrzeby."""
    from bpp.models import Wersja_Przeliczenia

    with transaction.atomic():
        Wersja_Przeliczenia.objects.get_or_create(nazwa=przeliczenie.nazwa)
        # Blokada wiersza: drugi worker poczeka, a potem zobaczy nową wersję.
        stan = Wersja_Przeliczenia.objects.select_for_update().get(
            nazwa=przeliczenie.nazwa
        )
        if stan.wersja >= przeliczenie.wersja:
            return None

        logger.warning(
            "Zlecam przeliczenie %s (%s): wersja w bazie %s, w kodzie %s",
            przeliczenie.nazwa,
            przeliczenie.opis,
            stan.wersja,
            przeliczenie.wersja,
        )
        oznaczono = przeliczenie.oznacz()
        stan.wersja = przeliczenie.wersja
        stan.zlecono = timezone.now()
        stan.oznaczono_rekordow = oznaczono
        stan.save()

    logger.warning(
        "Przeliczenie %s zlecone: %s rekordów w kolejce denorm (postęp: "
        "manage.py denorm_show_dirtyinstances_count)",
        przeliczenie.nazwa,
        oznaczono,
    )
    return oznaczono


def zlec_zalegle_przeliczenia(przeliczenia=PRZELICZENIA):
    """Zleca wszystkie zaległe przeliczenia. Zwraca ``{nazwa: liczba}`` dla
    zleconych. Wyjątek nie jest łapany — jego przeliczenie zostaje zaległe
    i zostanie ponowione przy następnym starcie workera."""
    return {p.nazwa: n for p in przeliczenia if (n := zlec_przeliczenie(p)) is not None}
