"""
Celery tasks for publication duplicate scanning.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

logger = get_task_logger(__name__)

# How often to update progress (every N publications)
PROGRESS_UPDATE_INTERVAL = 100

# Minimum similarity score to store as a candidate
MIN_SIMILARITY_TO_STORE = 0.80


def _check_doi_match(publication_doi, match, match_reasons):
    """Check if DOIs match and update match_reasons."""
    if not publication_doi:
        return 0.0
    if not hasattr(match, "doi") or not match.doi:
        return 0.0

    from import_common.normalization import normalize_doi

    if normalize_doi(publication_doi) == normalize_doi(match.doi):
        match_reasons.append("DOI")
        return 1.0
    return 0.0


def _check_isbn_match(publication_isbn, match, match_reasons):
    """Check if ISBNs match and update match_reasons."""
    if not publication_isbn:
        return 0.0
    if not hasattr(match, "isbn") or not match.isbn:
        return 0.0

    from import_common.normalization import normalize_isbn

    if normalize_isbn(publication_isbn) == normalize_isbn(match.isbn):
        match_reasons.append("ISBN")
        return 0.95
    return 0.0


def _check_www_match(publication_www, match, match_reasons):
    """Check if WWW URLs match and update match_reasons."""
    if not publication_www:
        return 0.0
    if not hasattr(match, "www") or not match.www:
        return 0.0

    from import_common.normalization import normalize_public_uri

    if normalize_public_uri(publication_www) == normalize_public_uri(match.www):
        match_reasons.append("WWW")
        return 0.90
    return 0.0


def _check_zrodlo_match(publication_zrodlo, match, match_reasons):
    """Check if sources match and update match_reasons."""
    if not publication_zrodlo:
        return 0.0
    if not hasattr(match, "zrodlo") or not match.zrodlo:
        return 0.0

    if publication_zrodlo.pk == match.zrodlo.pk:
        match_reasons.append("źródło")
        return 0.85
    return 0.0


def _calculate_match_similarity(publication, match, scan_run):
    """
    Calculate similarity score and determine match reasons.

    Returns:
        Tuple of (similarity_score, match_reasons) or (None, None) if no valid match.
    """
    doi = getattr(publication, "doi", None) if not scan_run.ignore_doi else None
    www = getattr(publication, "www", None) if not scan_run.ignore_www else None
    isbn = getattr(publication, "isbn", None) if not scan_run.ignore_isbn else None
    zrodlo = (
        getattr(publication, "zrodlo", None) if not scan_run.ignore_zrodlo else None
    )

    match_reasons = []
    similarity = 0.0

    similarity = max(similarity, _check_doi_match(doi, match, match_reasons))
    similarity = max(similarity, _check_isbn_match(isbn, match, match_reasons))
    similarity = max(similarity, _check_www_match(www, match, match_reasons))
    similarity = max(similarity, _check_zrodlo_match(zrodlo, match, match_reasons))

    # Handle title-only matches
    if not match_reasons:
        match_reasons.append("tytuł")
        similarity = getattr(match, "podobienstwo", 0.80)
        if isinstance(similarity, float) and similarity < MIN_SIMILARITY_TO_STORE:
            return None, None
    elif similarity < MIN_SIMILARITY_TO_STORE:
        similarity = getattr(match, "podobienstwo", similarity)

    return similarity, match_reasons


def _get_user_by_id(user_id):
    """Get user by ID, returning None if not found."""
    if not user_id:
        return None

    from bpp.models.profile import BppUser

    try:
        return BppUser.objects.get(pk=user_id)
    except BppUser.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found, continuing without user")
        return None


def _get_publications_to_scan(year_from, year_to):
    """
    Get all publications in the specified year range.

    Returns a list of (content_type, publication) tuples.
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    publications = []

    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)

    # Get Wydawnictwo_Ciagle publications
    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(
        rok__gte=year_from, rok__lte=year_to
    ).order_by("pk")
    for pub in ciagle_qs.iterator():
        publications.append((ct_ciagle, pub))

    # Get Wydawnictwo_Zwarte publications
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(
        rok__gte=year_from, rok__lte=year_to
    ).order_by("pk")
    for pub in zwarte_qs.iterator():
        publications.append((ct_zwarte, pub))

    return publications


def _find_duplicates_for_publication(
    publication,
    content_type,
    scan_run,
    processed_pairs,
):
    """
    Find duplicate candidates for a single publication.

    Args:
        publication: The publication to check
        content_type: ContentType of the publication
        scan_run: The scan run instance
        processed_pairs: Set of already processed pairs to avoid duplicates

    Returns:
        List of PublicationDuplicateCandidate instances to create
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    candidates = []
    title = publication.tytul_oryginalny
    year = publication.rok

    doi = getattr(publication, "doi", None) if not scan_run.ignore_doi else None
    www = getattr(publication, "www", None) if not scan_run.ignore_www else None
    isbn = getattr(publication, "isbn", None) if not scan_run.ignore_isbn else None
    zrodlo = (
        getattr(publication, "zrodlo", None) if not scan_run.ignore_zrodlo else None
    )

    for klass in [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]:
        match = _try_match_publication(
            klass, publication, title, year, doi, www, isbn, zrodlo
        )
        if match is None:
            continue

        match_ct = ContentType.objects.get_for_model(klass)
        if _is_same_publication(content_type, publication.pk, match_ct, match.pk):
            continue

        if _is_pair_already_processed(
            content_type, publication.pk, match_ct, match.pk, processed_pairs
        ):
            continue

        candidate = _create_candidate_if_valid(
            publication, content_type, match, match_ct, scan_run, title, year
        )
        if candidate:
            candidates.append(candidate)

    return candidates


def _try_match_publication(klass, publication, title, year, doi, www, isbn, zrodlo):
    """Try to find a matching publication using matchuj_publikacje."""
    from import_common.core import matchuj_publikacje

    try:
        return matchuj_publikacje(
            klass=klass,
            title=title,
            year=year,
            doi=doi,
            public_uri=www,
            isbn=isbn,
            zrodlo=zrodlo,
            DEBUG_MATCHOWANIE=False,
        )
    except Exception as e:
        logger.debug(f"Error matching publication {publication.pk}: {e}")
        return None


def _is_same_publication(content_type, pub_pk, match_ct, match_pk):
    """Check if the match is the same publication as the original."""
    return content_type == match_ct and pub_pk == match_pk


def _is_pair_already_processed(
    content_type, pub_pk, match_ct, match_pk, processed_pairs
):
    """Check if this pair has already been processed and add it if not."""
    pair_key = tuple(sorted([(content_type.pk, pub_pk), (match_ct.pk, match_pk)]))
    if pair_key in processed_pairs:
        return True
    processed_pairs.add(pair_key)
    return False


def _create_candidate_if_valid(
    publication, content_type, match, match_ct, scan_run, title, year
):
    """Create a PublicationDuplicateCandidate if the match is valid."""
    from .models import PublicationDuplicateCandidate

    similarity, match_reasons = _calculate_match_similarity(
        publication, match, scan_run
    )
    if similarity is None:
        return None

    return PublicationDuplicateCandidate(
        scan_run=scan_run,
        original_content_type=content_type,
        original_object_id=publication.pk,
        duplicate_content_type=match_ct,
        duplicate_object_id=match.pk,
        similarity_score=similarity,
        match_reasons=match_reasons,
        original_title=title[:2048] if title else "",
        duplicate_title=(match.tytul_oryginalny or "")[:2048],
        original_year=year,
        duplicate_year=match.rok,
        original_type=content_type.model,
        duplicate_type=match_ct.model,
    )


@shared_task(bind=True, name="deduplikator_publikacji.scan_for_duplicates")
def scan_for_duplicates(
    self,
    user_id=None,
    year_from=2022,
    year_to=2025,
    ignore_doi=False,
    ignore_www=False,
    ignore_isbn=False,
    ignore_zrodlo=False,
):
    """
    Background task to scan publications for potential duplicates.

    Args:
        user_id: Optional ID of the user who triggered the scan
        year_from: Start year for scanning
        year_to: End year for scanning
        ignore_doi: If True, don't use DOI for matching
        ignore_www: If True, don't use WWW for matching
        ignore_isbn: If True, don't use ISBN for matching
        ignore_zrodlo: If True, don't use source for matching

    Returns:
        dict: Result with status, scan_run_id, and statistics
    """
    from .models import PublicationDuplicateCandidate, PublicationDuplicateScanRun

    logger.info(
        f"Starting publication duplicate scan: years {year_from}-{year_to}, "
        f"ignore_doi={ignore_doi}, ignore_www={ignore_www}, "
        f"ignore_isbn={ignore_isbn}, ignore_zrodlo={ignore_zrodlo}"
    )

    user = _get_user_by_id(user_id)

    scan_run = PublicationDuplicateScanRun.objects.create(
        status=PublicationDuplicateScanRun.Status.RUNNING,
        created_by=user,
        celery_task_id=self.request.id or "",
        year_from=year_from,
        year_to=year_to,
        ignore_doi=ignore_doi,
        ignore_www=ignore_www,
        ignore_isbn=ignore_isbn,
        ignore_zrodlo=ignore_zrodlo,
    )

    try:
        # Delete previous candidates from this scan's year range
        deleted_count = (
            PublicationDuplicateCandidate.objects.filter(
                scan_run__year_from=year_from,
                scan_run__year_to=year_to,
            )
            .exclude(scan_run=scan_run)
            .delete()[0]
        )
        logger.info(f"Deleted {deleted_count} existing candidates")

        # Get publications to scan
        publications = _get_publications_to_scan(year_from, year_to)
        total_count = len(publications)

        scan_run.total_publications_to_scan = total_count
        scan_run.save(update_fields=["total_publications_to_scan"])

        logger.info(f"Scanning {total_count} publications for duplicates...")

        publications_scanned = 0
        duplicates_found = 0
        candidates_to_create = []
        processed_pairs = set()

        for content_type, publication in publications:
            # Check for cancellation
            scan_run.refresh_from_db()
            if scan_run.status == PublicationDuplicateScanRun.Status.CANCELLED:
                logger.info("Scan cancelled by user")
                return {
                    "status": "cancelled",
                    "scan_run_id": scan_run.pk,
                    "publications_scanned": publications_scanned,
                    "duplicates_found": duplicates_found,
                }

            publications_scanned += 1

            new_candidates = _find_duplicates_for_publication(
                publication,
                content_type,
                scan_run,
                processed_pairs,
            )
            candidates_to_create.extend(new_candidates)
            duplicates_found += len(new_candidates)

            # Bulk create candidates periodically
            if len(candidates_to_create) >= 500:
                with transaction.atomic():
                    PublicationDuplicateCandidate.objects.bulk_create(
                        candidates_to_create, ignore_conflicts=True
                    )
                candidates_to_create = []

            # Update progress periodically
            if publications_scanned % PROGRESS_UPDATE_INTERVAL == 0:
                scan_run.publications_scanned = publications_scanned
                scan_run.duplicates_found = duplicates_found
                scan_run.save(
                    update_fields=["publications_scanned", "duplicates_found"]
                )
                logger.info(
                    f"Progress: {publications_scanned}/{total_count} publications, "
                    f"{duplicates_found} duplicates found"
                )

        # Save remaining candidates
        if candidates_to_create:
            with transaction.atomic():
                PublicationDuplicateCandidate.objects.bulk_create(
                    candidates_to_create, ignore_conflicts=True
                )

        # Mark scan as completed
        scan_run.status = PublicationDuplicateScanRun.Status.COMPLETED
        scan_run.finished_at = timezone.now()
        scan_run.publications_scanned = publications_scanned
        scan_run.duplicates_found = duplicates_found
        scan_run.save()

        logger.info(
            f"Scan completed: {publications_scanned} publications scanned, "
            f"{duplicates_found} duplicates found"
        )

        return {
            "status": "success",
            "scan_run_id": scan_run.pk,
            "publications_scanned": publications_scanned,
            "duplicates_found": duplicates_found,
        }

    except Exception as e:
        logger.error(f"Error during duplicate scan: {str(e)}", exc_info=True)
        scan_run.status = PublicationDuplicateScanRun.Status.FAILED
        scan_run.finished_at = timezone.now()
        scan_run.error_message = str(e)
        scan_run.save()
        return {
            "status": "error",
            "scan_run_id": scan_run.pk,
            "error": str(e),
        }


@shared_task(name="deduplikator_publikacji.cancel_scan")
def cancel_scan(scan_run_id):
    """
    Cancel a running scan.

    Args:
        scan_run_id: ID of the PublicationDuplicateScanRun to cancel

    Returns:
        dict: Result with status
    """
    from .models import PublicationDuplicateScanRun

    try:
        scan_run = PublicationDuplicateScanRun.objects.get(pk=scan_run_id)

        if scan_run.status != PublicationDuplicateScanRun.Status.RUNNING:
            return {
                "status": "error",
                "error": f"Scan is not running (status: {scan_run.status})",
            }

        scan_run.status = PublicationDuplicateScanRun.Status.CANCELLED
        scan_run.finished_at = timezone.now()
        scan_run.save()

        logger.info(f"Scan {scan_run_id} marked for cancellation")
        return {"status": "success", "scan_run_id": scan_run_id}

    except PublicationDuplicateScanRun.DoesNotExist:
        return {"status": "error", "error": f"Scan run {scan_run_id} not found"}
