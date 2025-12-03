"""
Celery tasks for author duplicate scanning.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.utils import timezone

from .utils.constants import MAX_PEWNOSC, MIN_PEWNOSC

logger = get_task_logger(__name__)

# Minimum confidence to store a candidate (same as MIN_PEWNOSC_DO_WYSWIETLENIA in views.py)
MIN_CONFIDENCE_TO_STORE = 50

# How often to update progress (every N authors)
PROGRESS_UPDATE_INTERVAL = 100


def normalize_confidence(raw_score: int) -> float:
    """
    Normalize raw confidence score to 0.0-1.0 range.

    Args:
        raw_score: Raw confidence score (MIN_PEWNOSC to MAX_PEWNOSC)

    Returns:
        Normalized score between 0.0 and 1.0
    """
    # Shift to 0-based range
    shifted = raw_score - MIN_PEWNOSC
    total_range = MAX_PEWNOSC - MIN_PEWNOSC
    return max(0.0, min(1.0, shifted / total_range))


def _get_user_by_id(user_id):
    """
    Get user by ID, returning None if not found.

    Args:
        user_id: The user ID to look up

    Returns:
        BppUser instance or None
    """
    if not user_id:
        return None

    from bpp.models.profile import BppUser

    try:
        return BppUser.objects.get(pk=user_id)
    except BppUser.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found, continuing without user")
        return None


def calculate_author_priority(autor):
    """
    Calculate priority based on publication dates and disciplines.

    Priority values:
        100 - has 2022-2025 publications WITH disciplines assigned
        50 - has 2022-2025 publications (any)
        0 - no recent publications

    Args:
        autor: Autor instance

    Returns:
        int: Priority value (0, 50, or 100)
    """
    from bpp.models import Autor_Dyscyplina
    from bpp.models.cache import Rekord

    # Check for 2022-2025 publications
    recent_pubs = Rekord.objects.prace_autora(autor).filter(
        rok__gte=2022, rok__lte=2025
    )

    if not recent_pubs.exists():
        return 0

    # Check if author has disciplines in 2022-2025 period
    has_disciplines = Autor_Dyscyplina.objects.filter(
        autor=autor, rok__gte=2022, rok__lte=2025
    ).exists()

    if has_disciplines:
        return 100

    return 50


def _get_main_autor_from_osoba(osoba_z_instytucji):
    """
    Get the main Autor record from an OsobaZInstytucji.

    Args:
        osoba_z_instytucji: OsobaZInstytucji instance

    Returns:
        Autor instance or None if not available
    """
    if not osoba_z_instytucji.personId:
        return None

    scientist = osoba_z_instytucji.personId

    if not hasattr(scientist, "rekord_w_bpp") or not scientist.rekord_w_bpp:
        return None

    return scientist.rekord_w_bpp


def _process_duplicate_info(
    duplikat_info,
    scan_run,
    main_autor,
    osoba_z_instytucji,
    main_pub_count,
    min_confidence,
):
    """
    Process a single duplicate info entry and create a DuplicateCandidate if valid.

    Args:
        duplikat_info: Dictionary containing duplicate analysis info
        scan_run: The DuplicateScanRun instance
        main_autor: The main Autor instance
        osoba_z_instytucji: The OsobaZInstytucji instance
        main_pub_count: Publication count for main author
        min_confidence: Minimum confidence threshold

    Returns:
        DuplicateCandidate instance or None
    """
    from bpp.models.cache import Rekord

    from .models import DuplicateCandidate

    confidence_score = duplikat_info.get("pewnosc", 0)

    if confidence_score < min_confidence:
        return None

    duplicate_autor = duplikat_info.get("autor")
    if not duplicate_autor:
        return None

    dup_pub_count = Rekord.objects.prace_autora(duplicate_autor).count()

    # Calculate priority based on duplicate author's recent works
    priority = calculate_author_priority(duplicate_autor)

    return DuplicateCandidate(
        scan_run=scan_run,
        main_autor=main_autor,
        main_osoba_z_instytucji=osoba_z_instytucji,
        duplicate_autor=duplicate_autor,
        confidence_score=confidence_score,
        confidence_percent=normalize_confidence(confidence_score),
        reasons=duplikat_info.get("powody_podobienstwa", []),
        priority=priority,
        main_autor_name=str(main_autor),
        duplicate_autor_name=str(duplicate_autor),
        main_publications_count=main_pub_count,
        duplicate_publications_count=dup_pub_count,
    )


def _process_author_duplicates(osoba_z_instytucji, scan_run, min_confidence):
    """
    Process duplicates for a single author.

    Args:
        osoba_z_instytucji: OsobaZInstytucji instance to check
        scan_run: The DuplicateScanRun instance
        min_confidence: Minimum confidence threshold

    Returns:
        List of DuplicateCandidate instances to create
    """
    from bpp.models.cache import Rekord

    from .utils.analysis import analiza_duplikatow
    from .utils.search import szukaj_kopii

    main_autor = _get_main_autor_from_osoba(osoba_z_instytucji)
    if not main_autor:
        return []

    duplikaty = szukaj_kopii(osoba_z_instytucji)
    if not duplikaty.exists():
        return []

    analiza = analiza_duplikatow(osoba_z_instytucji)
    if "error" in analiza:
        return []

    main_pub_count = Rekord.objects.prace_autora(main_autor).count()
    candidates = []

    for duplikat_info in analiza.get("analiza", []):
        candidate = _process_duplicate_info(
            duplikat_info,
            scan_run,
            main_autor,
            osoba_z_instytucji,
            main_pub_count,
            min_confidence,
        )
        if candidate:
            candidates.append(candidate)

    return candidates


@shared_task(bind=True, name="deduplikator_autorow.scan_for_duplicates")
def scan_for_duplicates(self, user_id=None, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """
    Background task to scan all authors for potential duplicates.

    This task:
    1. Creates a DuplicateScanRun record
    2. Deletes all existing DuplicateCandidate records (replace mode)
    3. Iterates through all OsobaZInstytucji
    4. For each, calls szukaj_kopii() to find candidates
    5. For each candidate, calls analiza_duplikatow() and stores in DuplicateCandidate
    6. Updates progress periodically
    7. Marks run as completed

    Args:
        user_id: Optional ID of the user who triggered the scan
        min_confidence: Minimum confidence score to store a candidate (default: 50)

    Returns:
        dict: Result with status, scan_run_id, and statistics
    """
    from pbn_api.models import OsobaZInstytucji

    from .models import DuplicateCandidate, DuplicateScanRun, IgnoredAuthor

    logger.info("Starting duplicate scan task...")

    user = _get_user_by_id(user_id)

    scan_run = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.RUNNING,
        created_by=user,
        celery_task_id=self.request.id or "",
    )

    try:
        deleted_count = DuplicateCandidate.objects.all().delete()[0]
        logger.info(f"Deleted {deleted_count} existing candidates")

        ignored_scientist_ids = set(
            IgnoredAuthor.objects.values_list("scientist_id", flat=True)
        )

        osoby_query = OsobaZInstytucji.objects.select_related("personId").all()
        if ignored_scientist_ids:
            osoby_query = osoby_query.exclude(personId__pk__in=ignored_scientist_ids)

        total_count = osoby_query.count()
        scan_run.total_authors_to_scan = total_count
        scan_run.save(update_fields=["total_authors_to_scan"])

        logger.info(f"Scanning {total_count} authors for duplicates...")

        authors_scanned = 0
        duplicates_found = 0
        candidates_to_create = []

        for osoba_z_instytucji in osoby_query.iterator():
            scan_run.refresh_from_db()
            if scan_run.status == DuplicateScanRun.Status.CANCELLED:
                logger.info("Scan cancelled by user")
                return {
                    "status": "cancelled",
                    "scan_run_id": scan_run.pk,
                    "authors_scanned": authors_scanned,
                    "duplicates_found": duplicates_found,
                }

            authors_scanned += 1

            new_candidates = _process_author_duplicates(
                osoba_z_instytucji, scan_run, min_confidence
            )
            candidates_to_create.extend(new_candidates)
            duplicates_found += len(new_candidates)

            if len(candidates_to_create) >= 1000:
                with transaction.atomic():
                    DuplicateCandidate.objects.bulk_create(
                        candidates_to_create, ignore_conflicts=True
                    )
                candidates_to_create = []

            if authors_scanned % PROGRESS_UPDATE_INTERVAL == 0:
                scan_run.authors_scanned = authors_scanned
                scan_run.duplicates_found = duplicates_found
                scan_run.save(update_fields=["authors_scanned", "duplicates_found"])
                logger.info(
                    f"Progress: {authors_scanned}/{total_count} authors, "
                    f"{duplicates_found} duplicates found"
                )

        if candidates_to_create:
            with transaction.atomic():
                DuplicateCandidate.objects.bulk_create(
                    candidates_to_create, ignore_conflicts=True
                )

        scan_run.status = DuplicateScanRun.Status.COMPLETED
        scan_run.finished_at = timezone.now()
        scan_run.authors_scanned = authors_scanned
        scan_run.duplicates_found = duplicates_found
        scan_run.save()

        logger.info(
            f"Scan completed: {authors_scanned} authors scanned, "
            f"{duplicates_found} duplicates found"
        )

        return {
            "status": "success",
            "scan_run_id": scan_run.pk,
            "authors_scanned": authors_scanned,
            "duplicates_found": duplicates_found,
        }

    except Exception as e:
        logger.error(f"Error during duplicate scan: {str(e)}", exc_info=True)
        scan_run.status = DuplicateScanRun.Status.FAILED
        scan_run.finished_at = timezone.now()
        scan_run.error_message = str(e)
        scan_run.save()
        return {
            "status": "error",
            "scan_run_id": scan_run.pk,
            "error": str(e),
        }


@shared_task(name="deduplikator_autorow.cancel_scan")
def cancel_scan(scan_run_id):
    """
    Cancel a running scan.

    Args:
        scan_run_id: ID of the DuplicateScanRun to cancel

    Returns:
        dict: Result with status
    """
    from .models import DuplicateScanRun

    try:
        scan_run = DuplicateScanRun.objects.get(pk=scan_run_id)

        if scan_run.status != DuplicateScanRun.Status.RUNNING:
            return {
                "status": "error",
                "error": f"Scan is not running (status: {scan_run.status})",
            }

        scan_run.status = DuplicateScanRun.Status.CANCELLED
        scan_run.finished_at = timezone.now()
        scan_run.save()

        logger.info(f"Scan {scan_run_id} marked for cancellation")
        return {"status": "success", "scan_run_id": scan_run_id}

    except DuplicateScanRun.DoesNotExist:
        return {"status": "error", "error": f"Scan run {scan_run_id} not found"}
