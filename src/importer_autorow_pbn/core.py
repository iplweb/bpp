from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from import_common.core import matchuj_autora
from pbn_api.models import Scientist

from .models import CachedScientistMatch

# Cache validity period in days
CACHE_VALIDITY_DAYS = 7


def get_cache_status():
    """
    Check the status of the scientist match cache.

    Returns:
        tuple: (is_valid, last_computed, message)
            - is_valid (bool): True if cache is valid (exists and not expired)
            - last_computed (datetime|None): When cache was last computed
            - message (str|None): Error message if cache is invalid
    """
    latest = CachedScientistMatch.objects.aggregate(Max("computed_at"))[
        "computed_at__max"
    ]
    if not latest:
        return False, None, "Cache nie został jeszcze zbudowany"

    age = timezone.now() - latest
    if age > timedelta(days=CACHE_VALIDITY_DAYS):
        return False, latest, f"Cache wygasł ({age.days} dni temu)"

    return True, latest, None


def _get_legacy_pbn_id(scientist):
    """Extract legacy PBN ID from scientist object."""
    legacy_ids = scientist.value("object", "legacyIdentifiers", return_none=True)
    return legacy_ids[0] if legacy_ids else None


def rebuild_match_cache(operation):
    """
    Rebuild the scientist match cache.

    This function matches all PBN scientists to BPP authors and stores the results
    in the CachedScientistMatch model. Progress is reported via the operation object.

    Args:
        operation: MatchCacheRebuildOperation instance for progress tracking
    """
    scientists = Scientist.objects.filter(from_institution_api=True)
    operation.total_scientists = scientists.count()
    operation.save(update_fields=["total_scientists"])

    matches_count = 0

    for idx, scientist in enumerate(scientists.iterator(), 1):
        match = matchuj_autora(
            imiona=scientist.name,
            nazwisko=scientist.lastName,
            orcid=scientist.orcid,
            pbn_uid_id=scientist.pk,
            pbn_id=_get_legacy_pbn_id(scientist),
        )

        CachedScientistMatch.objects.update_or_create(
            scientist=scientist, defaults={"matched_autor": match}
        )

        if match:
            matches_count += 1

        # Update progress every 10 records
        if idx % 10 == 0:
            operation.processed_scientists = idx
            operation.matches_found = matches_count
            operation.save(update_fields=["processed_scientists", "matches_found"])

    # Final statistics
    operation.processed_scientists = operation.total_scientists
    operation.matches_found = matches_count
    operation.save(update_fields=["processed_scientists", "matches_found"])
