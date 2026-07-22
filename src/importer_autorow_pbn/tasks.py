from celery import shared_task
from celery_singleton import Singleton

from .core import get_cache_status
from .models import MatchCacheRebuildOperation

# Budżet czasu automatycznej przebudowy cache dopasowań PBN.
#
# Przebudowa iteruje przez wszystkich naukowców PBN i dla każdego szuka
# odpowiednika wśród autorów BPP, zapisując CachedScientistMatch. Wszystko
# lokalnie (dane PBN są już w bazie — bez odpytywania API PBN), więc koszt to
# CPU + zapisy, nie latencja sieci. Godzina to solidny zapas dla dużej
# uczelni.
#
# Limit ma tu podwójny sens: zadanie chodzi CODZIENNIE z beata, a cache i tak
# jest ważny 7 dni (CACHE_VALIDITY_DAYS), więc ubity przebieg zostanie
# spokojnie ponowiony następnej nocy — nie ma powodu, by zawis trzymał slot
# workera aż do `visibility_timeout` brokera (6 h).
AUTO_REBUILD_TIME_LIMIT = 60 * 60


@shared_task
def rebuild_match_cache_task(operation_pk):
    """
    Celery task to rebuild the scientist match cache.

    This task wraps the operation's task_perform() method which handles
    the full lifecycle: mark_started(), perform(), mark_finished_okay/error().

    Args:
        operation_pk: Primary key of MatchCacheRebuildOperation instance
    """
    operation = MatchCacheRebuildOperation.objects.get(pk=operation_pk)
    operation.task_perform()


@shared_task(
    # Singleton (zadanie bezargumentowe → lock globalny): dwa równoległe
    # przebiegi tworzyłyby dwie MatchCacheRebuildOperation i dublowały zapisy
    # do CachedScientistMatch.
    base=Singleton,
    # lock_expiry > time_limit: lock jest brany przy PUBLIKACJI zadania, a
    # twardy kill dopiero w `start + time_limit`. Gdy zadanie poczeka w
    # kolejce, lock wygasłby PRZED ubiciem — otwierając okno na duplikat.
    # +5 min pokrywa realistyczny czas oczekiwania w kolejce.
    lock_expiry=AUTO_REBUILD_TIME_LIMIT + 300,
    time_limit=AUTO_REBUILD_TIME_LIMIT,
    soft_time_limit=int(0.95 * AUTO_REBUILD_TIME_LIMIT),
)
def auto_rebuild_match_cache_task():
    """
    Automatic cache rebuild task - triggered by Celery Beat.

    This task checks if the cache needs refreshing and performs
    a rebuild if necessary. Uses the first superuser as the owner.

    Returns:
        str: Status message describing what was done
    """
    is_valid, _, _ = get_cache_status()
    if is_valid:
        return "Cache is still valid, skipping rebuild"

    from django.contrib.auth import get_user_model

    User = get_user_model()
    system_user = User.objects.filter(is_superuser=True).first()

    if not system_user:
        return "No superuser found, cannot create operation"

    operation = MatchCacheRebuildOperation.objects.create(owner=system_user)
    operation.task_perform()

    return f"Rebuilt cache: {operation.matches_found} matches found out of {operation.total_scientists}"
