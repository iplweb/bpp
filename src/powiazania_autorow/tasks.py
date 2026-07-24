from celery import shared_task
from celery.utils.log import get_task_logger
from celery_singleton import Singleton

logger = get_task_logger(__name__)

# Budżet czasu przeliczania powiązań autorów.
#
# Zadanie jest w całości SQL-owe: jeden INSERT..SELECT z trzema self-joinami
# po tabelach *_Autor (Ciągłe/Zwarte/Patenty) plus kopia do tabeli docelowej.
# Zero round-tripów do Pythona, zero ruchu sieciowego — realny czas to rząd
# sekund/minut nawet przy kilkuset tysiącach wpisów autorstwa. 30 minut to
# kilkunastokrotny zapas: jeśli zadanie tyle biegnie, to znak, że coś jest
# chore (zakleszczenie na locku, zdegenerowany plan), a nie że „dziś było
# więcej danych" — wtedy chcemy ubicia, nie czekania.
#
# Dlaczego to w ogóle musi mieć limit: bez `time_limit` zawieszone zadanie
# trzyma slot workera aż do `visibility_timeout` brokera (6 h, patrz
# CELERY_BROKER_TRANSPORT_OPTIONS w settings/base.py), a zadanie leci
# codziennie o 4:00 — jeden zawis zjadałby slot na całą dobę.
POWIAZANIA_TIME_LIMIT = 30 * 60


def _zlicz_wspolautorow(model_autorstwa, author, connections):
    """Zlicza współautorów `author` z jednego modelu autorstwa (*_Autor) do
    słownika `connections` (coauthor_id -> liczba wspólnych prac).

    Dwa zapytania na model (zamiast 1 + N): najpierw materializujemy listę
    ID prac autora, potem JEDNYM zapytaniem pobieramy wszystkich współautorów
    na tych pracach. Semantyka zliczania jest identyczna jak przy pętli po
    pojedynczych pracach — każde wystąpienie współautora (z pominięciem
    `autor_id is None`) zwiększa licznik o 1, więc dla współautora N
    wspólnych prac dostajemy N.
    """
    pub_ids = list(
        model_autorstwa.objects.filter(autor=author).values_list("rekord_id", flat=True)
    )
    # Pusta lista ID prac → puste IN, zapytanie zwróci 0 wierszy (pusta pętla).
    for coauthor_id in (
        model_autorstwa.objects.filter(rekord_id__in=pub_ids)
        .exclude(autor=author)
        .values_list("autor_id", flat=True)
    ):
        if coauthor_id:
            connections[coauthor_id] += 1


@shared_task(
    name="powiazania_autorow.calculate_author_connections",
    # Singleton (bez argumentów → lock i tak jest globalny): zadanie kasuje i
    # odtwarza CAŁĄ tabelę AuthorConnection, więc dwa równoległe przebiegi
    # deptałyby sobie po wynikach.
    base=Singleton,
    # lock_expiry > time_limit: lock jest brany przy PUBLIKACJI zadania, a
    # twardy kill dopiero w `start + time_limit`. Gdy zadanie poczeka w
    # kolejce, lock wygasłby PRZED ubiciem — otwierając okno na duplikat.
    # +5 min pokrywa realistyczny czas oczekiwania w kolejce.
    lock_expiry=POWIAZANIA_TIME_LIMIT + 300,
    time_limit=POWIAZANIA_TIME_LIMIT,
    soft_time_limit=int(0.95 * POWIAZANIA_TIME_LIMIT),
)
def calculate_author_connections_task():
    """
    Celery task to calculate author connections in the background.
    This task can be scheduled to run periodically.
    """
    from .core import calculate_author_connections

    logger.info("Starting author connections calculation task...")

    try:
        total_connections = calculate_author_connections()
        logger.info(f"Successfully calculated {total_connections} author connections")
        return {"status": "success", "total_connections": total_connections}
    except Exception as e:
        logger.error(f"Error calculating author connections: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}


@shared_task(name="powiazania_autorow.update_single_author_connections")
def update_single_author_connections_task(author_id):
    """
    Update connections for a single author.
    Useful when an author's publications are modified.
    """
    from collections import defaultdict

    from django.db import transaction
    from django.db.models import Q

    from bpp.models import (
        Autor,
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    from .models import AuthorConnection

    logger.info(f"Updating connections for author ID: {author_id}")

    try:
        # Get the author
        author = Autor.objects.get(pk=author_id)

        # Remove existing connections for this author
        AuthorConnection.objects.filter(
            Q(primary_author=author) | Q(secondary_author=author)
        ).delete()

        # Dictionary to store connections
        connections = defaultdict(int)

        # Zlicz współautorów ze wszystkich typów prac danego autora.
        for model_autorstwa in (
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
            Patent_Autor,
        ):
            _zlicz_wspolautorow(model_autorstwa, author, connections)

        # Create new connections
        with transaction.atomic():
            connections_to_create = []
            for coauthor_id, count in connections.items():
                if count > 0:
                    # Determine primary and secondary (smaller ID is primary)
                    if author_id < coauthor_id:
                        primary_id, secondary_id = author_id, coauthor_id
                    else:
                        primary_id, secondary_id = coauthor_id, author_id

                    connections_to_create.append(
                        AuthorConnection(
                            primary_author_id=primary_id,
                            secondary_author_id=secondary_id,
                            shared_publications_count=count,
                        )
                    )

            AuthorConnection.objects.bulk_create(
                connections_to_create, ignore_conflicts=True
            )

        logger.info(f"Updated {len(connections)} connections for author {author}")
        return {
            "status": "success",
            "author_id": author_id,
            "connections_updated": len(connections),
        }

    except Autor.DoesNotExist:
        logger.error(f"Author with ID {author_id} not found")
        return {"status": "error", "error": f"Author with ID {author_id} not found"}
    except Exception as e:
        logger.error(
            f"Error updating connections for author {author_id}: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "error": str(e)}
