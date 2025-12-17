"""
Centralized PBN data freshness checking utilities.

This module provides functions to check if PBN data is fresh enough
for various operations (comparison, import, deduplication, etc.).
"""

from datetime import timedelta

from django.utils import timezone

from .models import PbnDownloadTask, PbnInstitutionPeopleTask, PbnJournalsDownloadTask

DATA_FRESHNESS_MAX_AGE_DAYS = 7


def _check_task_freshness(
    task_model, data_name, max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS
):
    """
    Generic freshness check for a PBN download task model.

    Args:
        task_model: The task model class to check
        data_name: Human-readable name for error messages (e.g., "publikacji", "autorów")
        max_age_days: Maximum age in days before data is considered stale

    Returns:
        tuple: (is_fresh: bool, message: str or None, last_download: datetime or None)
    """
    task = task_model.objects.filter(status="completed").first()
    if not task:
        return False, f"Dane {data_name} PBN nigdy nie były pobrane", None

    if not task.completed_at:
        return False, f"Brak daty zakończenia pobierania danych {data_name} PBN", None

    age = timezone.now() - task.completed_at
    if age > timedelta(days=max_age_days):
        return (
            False,
            f"Dane {data_name} PBN są nieaktualne ({age.days} dni)",
            task.completed_at,
        )

    return True, None, task.completed_at


def is_pbn_publications_data_fresh(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Check if PBN publications/statements data is fresh.

    Used by: komparator_pbn, komparator_pbn_udzialy, komparator_publikacji_pbn

    Returns:
        tuple: (is_fresh: bool, message: str or None, last_download: datetime or None)
    """
    return _check_task_freshness(PbnDownloadTask, "publikacji", max_age_days)


def is_pbn_people_data_fresh(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Check if PBN people/scientists data is fresh.

    Used by: deduplikator_autorow, importer_autorow_pbn

    Returns:
        tuple: (is_fresh: bool, message: str or None, last_download: datetime or None)
    """
    return _check_task_freshness(PbnInstitutionPeopleTask, "autorów", max_age_days)


def is_pbn_journals_data_fresh(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Check if PBN journals/sources data is fresh.

    Used by: komparator_pbn, pbn_komparator_zrodel

    Returns:
        tuple: (is_fresh: bool, message: str or None, last_download: datetime or None)
    """
    return _check_task_freshness(PbnJournalsDownloadTask, "źródeł", max_age_days)


def is_all_pbn_data_fresh(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Check if ALL PBN data types are fresh.

    Used by: komparator_pbn (which needs all data types)

    Returns:
        tuple: (is_fresh: bool, stale_messages: list[str], last_downloads: dict)
    """
    stale_messages = []
    last_downloads = {}

    # Check publications
    pub_fresh, pub_msg, pub_date = is_pbn_publications_data_fresh(max_age_days)
    if not pub_fresh:
        stale_messages.append(pub_msg)
    last_downloads["publications"] = pub_date

    # Check people
    people_fresh, people_msg, people_date = is_pbn_people_data_fresh(max_age_days)
    if not people_fresh:
        stale_messages.append(people_msg)
    last_downloads["people"] = people_date

    # Check journals
    journals_fresh, journals_msg, journals_date = is_pbn_journals_data_fresh(
        max_age_days
    )
    if not journals_fresh:
        stale_messages.append(journals_msg)
    last_downloads["journals"] = journals_date

    is_fresh = pub_fresh and people_fresh and journals_fresh
    return is_fresh, stale_messages, last_downloads
