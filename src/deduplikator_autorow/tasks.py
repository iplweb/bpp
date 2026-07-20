"""
Celery tasks for author duplicate scanning.
"""

from datetime import timedelta

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import connection, transaction
from django.utils import timezone

from django_bpp.celery_tasks import GlobalSingleton
from django_bpp.db_locks import advisory_lock_id

from .utils.constants import MAX_PEWNOSC, MIN_PEWNOSC

logger = get_task_logger(__name__)

# Minimum confidence to store a candidate (same as MIN_PEWNOSC_DO_WYSWIETLENIA in views.py)
MIN_CONFIDENCE_TO_STORE = 50

# How often to update progress (every N authors)
PROGRESS_UPDATE_INTERVAL = 100

# Budżet czasu pełnego skanu duplikatów autorów.
#
# To najcięższe z zadań cyklicznych: dwie fazy (PBN + general) przechodzą
# przez wszystkich autorów, budują bucket-y i generują pary kandydatów z
# fuzzy-scoringiem. Bucketowanie ratuje przed pełnym O(n^2), ale przy dużym
# korpusie to i tak dziesiątki minut.
#
# 3 h to zapas na najgorszy realny przypadek, z dwoma twardymi sufitami:
#  * `visibility_timeout` brokera = 6 h — limit MUSI być wyraźnie niższy,
#    inaczej Redis re-dostarczy zadanie jeszcze w trakcie jego wykonywania
#    i dostaniemy dwa przebiegi „replace mode" naraz,
#  * start o 3:00 (crontab) — 3 h kończy przebieg przed 6:00, czyli przed
#    porannym ruchem użytkowników.
SCAN_TIME_LIMIT = 3 * 60 * 60

# Po tylu sekundach wpis DuplicateScanRun w statusie RUNNING uznajemy za
# osierocony (zombie). Worker ubija zadanie twardo po SCAN_TIME_LIMIT, więc
# przebieg starszy niż limit + margines NIE MOŻE już legalnie trwać — został
# po SIGKILL-u workera / OOM-ie, gdzie blok `except` nie miał szans się
# wykonać i przestawić statusu na FAILED.
#
# Margines jest po to, żeby nie ubić przebiegu, który właśnie dostaje
# SIGKILL-a i za moment sam się posprząta. Bez przeterminowania osierocony
# RUNNING zakleszczyłby skanowanie NA ZAWSZE — a to gorsze niż ryzyko, przed
# którym się bronimy.
SCAN_STALE_AFTER = SCAN_TIME_LIMIT + 15 * 60

# Klucz Postgresowego advisory locka chroniącego „slot" skanu duplikatów.
# Patrz `_przejmij_slot_skanu` — to on, a nie `select_for_update`, zapewnia
# wzajemne wykluczanie (na pustej tabeli nie ma wierszy do zablokowania).
#
# Wartość wyprowadzona deterministycznie (blake2s — patrz
# `django_bpp.db_locks`), żeby dało się ją odtworzyć i żeby nikt nie użył
# przypadkiem tej samej gdzie indziej.
#
# CELOWO nie `abs(hash(...))` — wbudowany `hash()` dla str jest solony
# PYTHONHASHSEED-em, więc daje INNĄ wartość w każdym procesie Pythona, a
# klucz liczony w ten sposób nie wyklucza niczego między workerami (każdy
# zakłada lock na własnym numerze).
#
# Wynik jest bit-w-bit tą samą liczbą (8081800802642310148) co wcześniejsza
# stała literalna — pilnuje tego test w `tests/test_advisory_lock_id.py`.
SCAN_SLOT_LOCK_ID = advisory_lock_id("deduplikator_autorow.scan_for_duplicates.slot")


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


def _calculate_priority_from_meta(meta_entry: dict) -> int:
    """Computes priority from meta dict (no SQL).

    Mirrors :func:`calculate_author_priority` but uses cached fields
    from the meta dict produced by ``build_autor_meta``. Avoids
    per-candidate SQL on the hot path of ``_run_general_phase``.

    Priority values:
        100 - has 2022-2025 publications WITH disciplines
        50 - has 2022-2025 publications (any)
        0 - no recent publications

    TODO: ``calculate_author_priority`` checks disciplines specifically
    in 2022-2025 (``Autor_Dyscyplina.objects.filter(rok__gte=2022,
    rok__lte=2025)``). The meta-cache only stores ``ma_dyscypline``
    (any year), so this is an approximation. Acceptable for v1 since
    priority is a sort hint, not a correctness invariant. To achieve
    exact parity, store year-filtered discipline data in meta.
    """
    recent_lata = {rok for rok in meta_entry["lata_publikacji"] if 2022 <= rok <= 2025}
    if not recent_lata:
        return 0
    if meta_entry["ma_dyscypline"]:
        return 100
    return 50


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


def _run_general_phase(scan_run, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Faza 2 skanu — duplikaty general (no SQL on hot path).

    Algorytm:
    1. build_autor_meta + build_buckets — pre-load wszystkich autorów.
    2. Read IgnoredAuthor / NotADuplicate exclusions.
    3. generate_pairs — pary score >= min_confidence.
    4. find_clusters — connected components.
    5. Cluster-skip jeśli ktokolwiek w klastrze ma OsobaZInstytucji.
    6. Pick main przez hierarchię B; emit pary (main, dup) jako
       DuplicateCandidate(scan_mode='general').
    7. Sprawdza scan_run.status == CANCELLED między batchami.
    """
    from .models import (
        DuplicateCandidate,
        DuplicateScanRun,
        IgnoredAuthor,
        NotADuplicate,
    )
    from .utils.analysis_meta import analiza_pary_meta
    from .utils.cluster import find_clusters
    from .utils.main_selection import pick_main_pk
    from .utils.meta import build_autor_meta, build_buckets
    from .utils.search_general import generate_pairs

    logger.info("General phase: building meta cache...")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    logger.info("General phase: %d autorów, %d bucketów", len(meta), len(buckets))

    ignored_pks = set(IgnoredAuthor.objects.values_list("autor_id", flat=True))
    notadup_pks = set(NotADuplicate.objects.values_list("autor_id", flat=True))

    pairs_data: dict[tuple[int, int], tuple[int, list[str]]] = {}
    for pk_a, pk_b, score, reasons in generate_pairs(
        buckets, meta, ignored_pks, notadup_pks, min_confidence
    ):
        pairs_data[(pk_a, pk_b)] = (score, reasons)
    logger.info("General phase: znaleziono %d par", len(pairs_data))

    clusters = find_clusters(list(pairs_data.keys()))
    logger.info("General phase: %d klastrów wstępnych", len(clusters))

    skipped_count = 0
    candidates_to_create: list[DuplicateCandidate] = []
    for cluster in clusters:
        if any(meta[pk]["ma_osoba_z_instytucji"] for pk in cluster):
            skipped_count += 1
            continue
        main_pk = pick_main_pk(cluster, meta)
        for dup_pk in cluster - {main_pk}:
            key = (min(main_pk, dup_pk), max(main_pk, dup_pk))
            if key in pairs_data:
                score, reasons = pairs_data[key]
            else:
                score, reasons = analiza_pary_meta(meta[main_pk], meta[dup_pk])
            main_obj = meta[main_pk]["obj"]
            dup_obj = meta[dup_pk]["obj"]
            candidates_to_create.append(
                DuplicateCandidate(
                    scan_run=scan_run,
                    main_autor=main_obj,
                    duplicate_autor=dup_obj,
                    confidence_score=score,
                    confidence_percent=normalize_confidence(score),
                    reasons=reasons,
                    priority=_calculate_priority_from_meta(meta[dup_pk]),
                    main_autor_name=str(main_obj),
                    duplicate_autor_name=str(dup_obj),
                    main_publications_count=meta[main_pk]["publikacje_count"],
                    duplicate_publications_count=meta[dup_pk]["publikacje_count"],
                    scan_mode="general",
                )
            )
            if len(candidates_to_create) >= 1000:
                with transaction.atomic():
                    DuplicateCandidate.objects.bulk_create(
                        candidates_to_create, ignore_conflicts=True
                    )
                candidates_to_create = []
                scan_run.refresh_from_db()
                if scan_run.status == DuplicateScanRun.Status.CANCELLED:
                    logger.info("General phase cancelled mid-batch")
                    return

    if candidates_to_create:
        with transaction.atomic():
            DuplicateCandidate.objects.bulk_create(
                candidates_to_create, ignore_conflicts=True
            )

    logger.info(
        "General phase: %d klastrów pominiętych (z OsobaZInstytucji)",
        skipped_count,
    )


def _run_pbn_phase(scan_run, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Faza 1 skanu — duplikaty PBN (OsobaZInstytucji).

    Iteruje przez wszystkie OsobaZInstytucji (z wyjątkiem IgnoredScientist),
    dla każdej szuka kopii (`szukaj_kopii`), analizuje (`analiza_duplikatow`)
    i tworzy DuplicateCandidate. Polluje `scan_run.status` między autorami —
    jeśli zewnętrzny `cancel_scan` ustawił CANCELLED, kończy wcześnie
    (status pozostaje CANCELLED — caller decyduje o finalizacji).

    Aktualizuje pola `total_authors_to_scan`, `authors_scanned` i
    `duplicates_found` na `scan_run` w trakcie pracy.
    """
    from pbn_api.models import OsobaZInstytucji

    from .models import DuplicateCandidate, DuplicateScanRun, IgnoredScientist

    ignored_scientist_ids = set(
        IgnoredScientist.objects.values_list("scientist_id", flat=True)
    )

    osoby_query = OsobaZInstytucji.objects.select_related("personId").all()
    if ignored_scientist_ids:
        osoby_query = osoby_query.exclude(personId__pk__in=ignored_scientist_ids)

    total_count = osoby_query.count()
    scan_run.total_authors_to_scan = total_count
    scan_run.save(update_fields=["total_authors_to_scan"])

    logger.info(f"PBN phase: scanning {total_count} authors...")

    authors_scanned = 0
    duplicates_found = 0
    candidates_to_create = []

    for osoba_z_instytucji in osoby_query.iterator():
        scan_run.refresh_from_db()
        if scan_run.status == DuplicateScanRun.Status.CANCELLED:
            logger.info("PBN phase cancelled by user")
            if candidates_to_create:
                with transaction.atomic():
                    DuplicateCandidate.objects.bulk_create(
                        candidates_to_create, ignore_conflicts=True
                    )
            scan_run.authors_scanned = authors_scanned
            scan_run.duplicates_found = duplicates_found
            scan_run.save(update_fields=["authors_scanned", "duplicates_found"])
            return

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
                f"PBN progress: {authors_scanned}/{total_count} authors, "
                f"{duplicates_found} duplicates found"
            )

    if candidates_to_create:
        with transaction.atomic():
            DuplicateCandidate.objects.bulk_create(
                candidates_to_create, ignore_conflicts=True
            )

    scan_run.authors_scanned = authors_scanned
    scan_run.duplicates_found = duplicates_found
    scan_run.save(update_fields=["authors_scanned", "duplicates_found"])

    logger.info(
        f"PBN phase done: {authors_scanned} authors scanned, "
        f"{duplicates_found} duplicates found"
    )


def _przejmij_slot_skanu(user, celery_task_id):
    """Atomowo zajmij „slot" skanu: zwróć nowy DuplicateScanRun albo None.

    Druga — NIEZALEŻNA OD REDISA — warstwa ochrony przed równoległymi
    przebiegami. Lock `GlobalSingleton` sam nie wystarcza, bo
    `unlock_all`/`clear_locks` na sygnale `worker_ready`
    (django_bpp/celery_tasks.py) kasuje WSZYSTKIE locki globalnie: przy
    wielu kontenerach workera rolling restart któregokolwiek z nich zwalnia
    w środku 3-godzinnego skanu lock chroniący przebieg trwający na INNYM
    workerze. Bez tej bariery drugi przebieg wszedłby w
    `DuplicateCandidate.objects.all().delete()` i skasował wyniki pierwszego.

    Zwraca None, gdy trwa już świeży skan (wołający ma się wycofać).

    Wpisy RUNNING starsze niż SCAN_STALE_AFTER są przeterminowywane na FAILED
    — inaczej jeden SIGKILL workera zakleszczyłby skanowanie na zawsze.

    Wzajemne wykluczanie stoi na `pg_advisory_xact_lock`, NIE na
    `select_for_update`. To istotne: `SELECT ... FOR UPDATE` blokuje
    ZNALEZIONE wiersze, a gdy żaden skan nie trwa, zbiór wynikowy jest PUSTY —
    nie ma czego zablokować i wszystkie równoległe transakcje przechodzą dalej,
    każda tworząc własny wpis RUNNING (phantom read). Czyli dokładnie w
    jedynym momencie, w którym bariera ma coś robić, `select_for_update` jest
    dekoracją. Advisory lock jest zakładany na UMOWNYM obiekcie, który istnieje
    niezależnie od wierszy, więc działa też przy pustej tabeli. Wariant
    `_xact_` zwalnia się sam na COMMIT/ROLLBACK i przy zerwaniu połączenia,
    więc nie wprowadza nowej klasy zombie.
    """
    from .models import DuplicateScanRun

    stale_cutoff = timezone.now() - timedelta(seconds=SCAN_STALE_AFTER)

    with transaction.atomic():
        # MUSI być pierwszą instrukcją w transakcji — cała sekcja krytyczna
        # (odczyt RUNNING + decyzja + INSERT) ma być pod tym lockiem.
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", [SCAN_SLOT_LOCK_ID])

        running = list(
            DuplicateScanRun.objects.filter(
                status=DuplicateScanRun.Status.RUNNING
            ).order_by("pk")
        )

        zywe = [r for r in running if r.started_at > stale_cutoff]
        osierocone = [r for r in running if r.started_at <= stale_cutoff]

        for zombie in osierocone:
            zombie.status = DuplicateScanRun.Status.FAILED
            zombie.finished_at = timezone.now()
            zombie.error_message = (
                f"Przebieg porzucony: status RUNNING utrzymywał się dłużej niż "
                f"{SCAN_STALE_AFTER}s (prawdopodobnie ubity worker). "
                f"Przeterminowany automatycznie przy starcie kolejnego skanu."
            )
            zombie.save(update_fields=["status", "finished_at", "error_message"])
            logger.warning(
                "Przeterminowano osierocony DuplicateScanRun pk=%s (started_at=%s)",
                zombie.pk,
                zombie.started_at,
            )

        if zywe:
            logger.warning(
                "Skan duplikatów już trwa (DuplicateScanRun pk=%s, "
                "started_at=%s) — pomijam to uruchomienie.",
                zywe[0].pk,
                zywe[0].started_at,
            )
            return None

        return DuplicateScanRun.objects.create(
            status=DuplicateScanRun.Status.RUNNING,
            created_by=user,
            celery_task_id=celery_task_id,
        )


@shared_task(
    bind=True,
    name="deduplikator_autorow.scan_for_duplicates",
    # GlobalSingleton, nie Singleton: zadanie bierze `user_id`, a zwykły
    # Singleton kluczuje lock po argumentach — dwóch użytkowników klikających
    # „skanuj" dostałoby dwa równoległe przebiegi, a każdy zaczyna od
    # `DuplicateCandidate.objects.all().delete()`. Lock musi być globalny.
    #
    # Lock w Redisie to jednak TYLKO pierwsza warstwa — `clear_locks` na
    # `worker_ready` kasuje go przy restarcie dowolnego workera. Druga,
    # niezależna warstwa siedzi w `_przejmij_slot_skanu` (bariera w bazie).
    base=GlobalSingleton,
    # lock_expiry > time_limit: lock jest brany przy PUBLIKACJI zadania, a
    # twardy kill dopiero w `start + time_limit`. Gdy zadanie poczeka w
    # kolejce, lock wygasłby PRZED ubiciem — i otworzył okno na duplikat.
    # +5 min pokrywa realistyczny czas oczekiwania w kolejce.
    lock_expiry=SCAN_TIME_LIMIT + 300,
    time_limit=SCAN_TIME_LIMIT,
    soft_time_limit=int(0.95 * SCAN_TIME_LIMIT),
)
def scan_for_duplicates(self, user_id=None, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Combined task: faza PBN + faza general w jednym przebiegu.

    Statusy końcowe:
    - COMPLETED: obie fazy ukończone.
    - PARTIAL_COMPLETED: faza PBN OK, faza general anulowana → wyniki PBN
      dostępne.
    - CANCELLED: faza PBN anulowana → brak wyników.
    - FAILED: nieobsłużony wyjątek.
    """
    from .models import DuplicateCandidate, DuplicateScanRun

    logger.info("Starting duplicate scan task (combined PBN + general)...")

    user = _get_user_by_id(user_id)
    scan_run = _przejmij_slot_skanu(user, self.request.id or "")
    if scan_run is None:
        # Inny przebieg trwa — wycofujemy się PRZED skasowaniem kandydatów.
        return {"status": "already_running"}

    try:
        # Replace mode: clear all previous candidates
        deleted_count = DuplicateCandidate.objects.all().delete()[0]
        logger.info(f"Deleted {deleted_count} existing candidates")

        # FAZA 1: PBN
        scan_run.phase = "pbn"
        scan_run.save(update_fields=["phase"])
        _run_pbn_phase(scan_run, min_confidence)
        scan_run.refresh_from_db()
        if scan_run.status == DuplicateScanRun.Status.CANCELLED:
            scan_run.finished_at = timezone.now()
            scan_run.save(update_fields=["finished_at"])
            logger.info("Scan cancelled in PBN phase")
            return {
                "status": "cancelled",
                "scan_run_id": scan_run.pk,
            }

        # FAZA 2: general
        scan_run.phase = "general"
        scan_run.save(update_fields=["phase"])
        _run_general_phase(scan_run, min_confidence)
        scan_run.refresh_from_db()
        if scan_run.status == DuplicateScanRun.Status.CANCELLED:
            scan_run.status = DuplicateScanRun.Status.PARTIAL_COMPLETED
            scan_run.finished_at = timezone.now()
            scan_run.save(update_fields=["status", "finished_at"])
            logger.info("Scan cancelled in general phase → PARTIAL_COMPLETED")
            return {
                "status": "partial_completed",
                "scan_run_id": scan_run.pk,
            }

        total_cands = DuplicateCandidate.objects.filter(scan_run=scan_run).count()
        scan_run.status = DuplicateScanRun.Status.COMPLETED
        scan_run.finished_at = timezone.now()
        scan_run.duplicates_found = total_cands
        scan_run.save()

        logger.info(
            f"Scan completed: {scan_run.authors_scanned} authors scanned, "
            f"{total_cands} duplicates found"
        )

        return {
            "status": "success",
            "scan_run_id": scan_run.pk,
            "duplicates_found": total_cands,
        }

    except Exception as e:
        logger.exception("Error during duplicate scan")
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
