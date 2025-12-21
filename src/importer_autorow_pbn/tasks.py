from celery import shared_task

from .core import get_cache_status
from .models import MatchCacheRebuildOperation


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


@shared_task
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
