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

# How many times (per publication model) matchuj_publikacje is asked for
# a match of one publication by identifiers (DOI, source, ISBN, WWW -- all
# cheap, indexed lookups). Every match found is excluded from the next
# lookup, so the search stops after one lookup for the vast majority of
# publications, which have no duplicate at all; the cap bounds the number
# of queries for "popular" titles.
MAX_MATCHES_PER_MODEL = 3

# How many most similar titles (per publication model, same year) are
# reported by the title-similarity query -- the only expensive query.
MAX_TITLE_MATCHES_PER_MODEL = 5
# How many rows the title query fetches before the part-number check
# ("cz. II" vs "cz. III") filters them in Python.
TITLE_QUERY_LIMIT = 10

# Cheap pre-filter for the title query: titles whose length differs too much
# cannot reach MIN_SIMILARITY_TO_STORE, so trigram similarity is not computed
# for them. A heuristic with a wide margin.
TITLE_LENGTH_MIN_RATIO = 0.7
TITLE_LENGTH_MAX_RATIO = 1.45


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
        match_ct = ContentType.objects.get_for_model(klass)

        # Never match the publication with itself: for a record of the same
        # type the best match is almost always the record itself, which used
        # to hide the real duplicate (FD#603).
        exclude_pks = set()
        if match_ct == content_type:
            exclude_pks.add(publication.pk)

        # Matches by identifiers (DOI, source, ISBN, WWW) ...
        matches = []
        for _ in range(MAX_MATCHES_PER_MODEL):
            match = _try_match_publication(
                klass, publication, title, year, doi, www, isbn, zrodlo, exclude_pks
            )
            if match is None:
                break
            exclude_pks.add(match.pk)
            matches.append(match)

        # ... and the most similar titles from the same year.
        matches.extend(_find_title_matches(klass, title, year, exclude_pks))

        for match in matches:
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


def _find_title_matches(klass, title, year, exclude_pks):
    """Return up to MAX_TITLE_MATCHES_PER_MODEL records of ``klass`` from
    ``year`` with a title at least MIN_SIMILARITY_TO_STORE similar to
    ``title``, most similar first (annotated with ``podobienstwo``).

    Uses the same title normalization and trigram similarity as
    matchuj_publikacje, but -- unlike it -- returns several records and
    accepts slightly less similar titles: the deduplicator only suggests
    pairs, an editor decides.
    """
    from django.contrib.postgres.search import TrigramSimilarity
    from django.db.models.functions import Length

    from import_common.core.normalize_db import normalized_db_title
    from import_common.core.publikacja import (
        _is_title_long_enough,
        _part_numbers_compatible,
    )
    from import_common.normalization import normalize_tytul_publikacji

    title = normalize_tytul_publikacji(title)
    if not _is_title_long_enough(title):
        return []

    length = len(title)
    qs = (
        klass.objects.filter(rok=year)
        .exclude(pk__in=list(exclude_pks))
        .annotate(dlugosc_tytulu=Length("tytul_oryginalny"))
        .filter(
            dlugosc_tytulu__gte=int(length * TITLE_LENGTH_MIN_RATIO),
            dlugosc_tytulu__lte=int(length * TITLE_LENGTH_MAX_RATIO) + 1,
        )
        .annotate(podobienstwo=TrigramSimilarity(normalized_db_title, title.lower()))
        .filter(podobienstwo__gte=MIN_SIMILARITY_TO_STORE)
        .order_by("-podobienstwo", "pk")[:TITLE_QUERY_LIMIT]
    )
    return [
        match for match in qs if _part_numbers_compatible(title, match.tytul_oryginalny)
    ][:MAX_TITLE_MATCHES_PER_MODEL]


def _try_match_publication(
    klass, publication, title, year, doi, www, isbn, zrodlo, exclude_pks=None
):
    """Try to find a matching publication using matchuj_publikacje.

    Records whose primary keys are in ``exclude_pks`` are never returned.
    """
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
            exclude_pks=exclude_pks,
            # Title similarity is checked by _find_title_matches (once,
            # returning several records) -- do not run it twice.
            matchuj_po_tytule=False,
        )
    except Exception:
        # One malformed record must not stop the whole scan; log it with
        # the traceback and carry on with the next publication.
        logger.exception(f"Error matching publication {publication.pk}")
        return None


def _is_same_publication(content_type, pub_pk, match_ct, match_pk):
    """Check if the match is the same publication as the original."""
    return content_type == match_ct and pub_pk == match_pk


def _is_pair_already_processed(
    content_type, pub_pk, match_ct, match_pk, processed_pairs
):
    """Check if this pair has already been processed and add it if not."""
    pair_key = _pair_key(content_type.pk, pub_pk, match_ct.pk, match_pk)
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


def _pair_key(content_type_id, pub_pk, match_ct_id, match_pk):
    """Direction-independent key of a publication pair."""
    return tuple(sorted([(content_type_id, pub_pk), (match_ct_id, match_pk)]))


def _get_rejected_pairs():
    """Return keys of all pairs marked as "not a duplicate" (in any scan)."""
    from .models import PublicationDuplicateCandidate

    return {
        _pair_key(*row)
        for row in PublicationDuplicateCandidate.objects.filter(
            status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE
        ).values_list(
            "original_content_type_id",
            "original_object_id",
            "duplicate_content_type_id",
            "duplicate_object_id",
        )
    }


def _delete_rejected_pending(scan_run):
    """Delete pending candidates of ``scan_run`` whose pair has been marked
    as "not a duplicate". Returns the number of deleted candidates."""
    from .models import PublicationDuplicateCandidate

    rejected = _get_rejected_pairs()
    if not rejected:
        return 0

    pending = PublicationDuplicateCandidate.objects.filter(
        scan_run=scan_run, status=PublicationDuplicateCandidate.Status.PENDING
    ).values_list(
        "pk",
        "original_content_type_id",
        "original_object_id",
        "duplicate_content_type_id",
        "duplicate_object_id",
    )
    to_delete = [pk for pk, *pair in pending if _pair_key(*pair) in rejected]
    if not to_delete:
        return 0
    return PublicationDuplicateCandidate.objects.filter(pk__in=to_delete).delete()[0]


def _delete_orphaned_decisions():
    """Delete "not a duplicate" decisions about publications that no longer
    exist (e.g. a record of the pair was deleted)."""
    from django.db.models import Exists, OuterRef

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    from .models import PublicationDuplicateCandidate

    decisions = PublicationDuplicateCandidate.objects.filter(
        status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE
    )
    models = [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]
    cts = ContentType.objects.get_for_models(*models)

    deleted_count = 0
    for model in models:
        ct = cts[model]
        for side in ("original", "duplicate"):
            deleted_count += (
                decisions.filter(**{f"{side}_content_type": ct})
                .exclude(Exists(model.objects.filter(pk=OuterRef(f"{side}_object_id"))))
                .delete()[0]
            )
    if deleted_count:
        logger.info(f"Deleted {deleted_count} decisions about removed records")


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
        # Delete previous candidates from this scan's year range, but keep
        # the "not a duplicate" decisions -- they must survive a rescan.
        deleted_count = (
            PublicationDuplicateCandidate.objects.filter(
                scan_run__year_from=year_from,
                scan_run__year_to=year_to,
            )
            .exclude(scan_run=scan_run)
            .exclude(status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE)
            .delete()[0]
        )
        logger.info(f"Deleted {deleted_count} existing candidates")

        _delete_orphaned_decisions()

        # Pairs rejected earlier ("Nie jest duplikatem") are treated as
        # already processed, so they will not be offered again.
        processed_pairs = _get_rejected_pairs()

        # Get publications to scan
        publications = _get_publications_to_scan(year_from, year_to)
        total_count = len(publications)

        scan_run.total_publications_to_scan = total_count
        scan_run.save(update_fields=["total_publications_to_scan"])

        logger.info(f"Scanning {total_count} publications for duplicates...")

        publications_scanned = 0
        duplicates_found = 0
        candidates_to_create = []

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

        # Pairs rejected by an editor while this scan was running (the
        # snapshot in processed_pairs predates them) must not come back.
        duplicates_found -= _delete_rejected_pending(scan_run)

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
