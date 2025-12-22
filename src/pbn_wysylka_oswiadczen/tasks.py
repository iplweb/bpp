import json
import time
import traceback

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from queryset_sequence import QuerySetSequence

from bpp.models import Uczelnia, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.client import PBNClient, RequestsTransport
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    DaneLokalneWymagajaAktualizacjiException,
    HttpException,
    PraceSerwisoweException,
)


def get_publications_queryset(rok_od=2022, rok_do=2025, tytul=None):
    """
    Get publications that need statements sent to PBN.

    Criteria:
    - rok in range [rok_od, rok_do]
    - has pbn_uid_id (synced with PBN)
    - has at least one author with:
      - dyscyplina_naukowa is not NULL
      - zatrudniony=True
      - afiliuje=True
      - jednostka != Uczelnia.obca_jednostka
    - (optional) title contains search text (case-insensitive)
    """
    uczelnia = Uczelnia.objects.get_default()
    obca_jednostka_id = uczelnia.obca_jednostka_id if uczelnia else None

    base_filter = {
        "rok__gte": rok_od,
        "rok__lte": rok_do,
        "pbn_uid_id__isnull": False,
        "autorzy_set__dyscyplina_naukowa__isnull": False,
        "autorzy_set__zatrudniony": True,
        "autorzy_set__afiliuje": True,
    }

    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(**base_filter).select_related(
        "pbn_uid"
    )
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(**base_filter).select_related(
        "pbn_uid"
    )

    # Exclude foreign unit if set
    if obca_jednostka_id:
        ciagle_qs = ciagle_qs.exclude(autorzy_set__jednostka_id=obca_jednostka_id)
        zwarte_qs = zwarte_qs.exclude(autorzy_set__jednostka_id=obca_jednostka_id)

    # Apply title filter if provided
    if tytul:
        ciagle_qs = ciagle_qs.filter(tytul_oryginalny__icontains=tytul)
        zwarte_qs = zwarte_qs.filter(tytul_oryginalny__icontains=tytul)

    return ciagle_qs.distinct(), zwarte_qs.distinct()


def get_pbn_client(user):
    """
    Create a PBN client for the given user.

    Args:
        user: Django user with PBN token

    Returns:
        PBNClient: Configured PBN API client

    Raises:
        ValueError: If configuration is invalid
    """
    pbn_user = user.get_pbn_user()

    if not pbn_user.pbn_token:
        raise ValueError("Uzytkownik nie ma tokenu PBN. Zaloguj sie do PBN.")

    if not pbn_user.pbn_token_possibly_valid():
        raise ValueError("Token PBN wygasl. Zaloguj sie ponownie do PBN.")

    uczelnia = Uczelnia.objects.get_default()
    if not uczelnia:
        raise ValueError("Brak domyslnej uczelni w systemie.")

    app_id = uczelnia.pbn_app_name
    app_token = uczelnia.pbn_app_token
    base_url = uczelnia.pbn_api_root

    if not all([app_id, app_token, base_url]):
        raise ValueError(
            "Ustawienia PBN uczelni niekompletne (brak app_id, app_token lub base_url)"
        )

    transport = RequestsTransport(app_id, app_token, base_url, pbn_user.pbn_token)
    return PBNClient(transport)


def _delete_existing_statements(publication, pbn_client, log_entry):
    """
    Delete existing statements for a publication from PBN.

    Args:
        publication: Publication instance
        pbn_client: PBN API client
        log_entry: Log entry to update on error

    Returns:
        None (updates log_entry on error)
    """
    try:
        pbn_client.delete_all_publication_statements(publication.pbn_uid_id)
        time.sleep(0.3)  # Small delay after delete
    except CannotDeleteStatementsException:
        # OK - statements didn't exist
        pass
    except PraceSerwisoweException:
        raise  # Propagate to main handler
    except HttpException as e:
        # Log the delete error but continue
        log_entry.error_message = f"Blad usuwania oswiadczen: {str(e)}"
        # Don't fail here, try to send anyway


def _handle_http_400_error(e, log_entry):
    """Handle HTTP 400 Bad Request error."""
    try:
        error_json = json.loads(e.content)
        log_entry.json_response = error_json
    except json.JSONDecodeError:
        log_entry.json_response = {"raw_error": str(e.content)[:1000]}

    log_entry.error_message = f"HTTP 400: {str(e)}"
    log_entry.save()
    return "error", log_entry


def _send_statements_with_retry(pbn_client, json_data, log_entry):
    """
    Send statements to PBN with retry logic.

    Args:
        pbn_client: PBN API client
        json_data: JSON data to send
        log_entry: Log entry to update

    Returns:
        tuple: (status, log_entry)
    """
    max_retries = 5
    retry_count = 0
    last_error = None

    while retry_count < max_retries:
        try:
            response = pbn_client.post_discipline_statements({"data": [json_data]})
            log_entry.json_response = response if response else {}
            log_entry.status = "success"
            log_entry.retry_count = retry_count
            log_entry.save()
            return "success", log_entry

        except HttpException as e:
            last_error = e
            retry_count += 1
            log_entry.retry_count = retry_count

            if e.status_code == 500:
                # Server error - retry with backoff
                time.sleep(2**retry_count)  # Exponential backoff: 2, 4, 8, 16, 32
                continue
            elif e.status_code == 423:
                # Resource locked - retry with delay
                time.sleep(2)
                continue
            elif e.status_code == 400:
                return _handle_http_400_error(e, log_entry)
            else:
                # Other HTTP error
                log_entry.error_message = f"HTTP {e.status_code}: {str(e)}"
                log_entry.save()
                return "error", log_entry

        except PraceSerwisoweException:
            log_entry.error_message = "Prace serwisowe w PBN - spróbuj ponownie później"
            log_entry.status = "maintenance"
            log_entry.save()
            raise  # Propagate to main handler

        except Exception as e:
            last_error = e
            retry_count += 1
            log_entry.retry_count = retry_count

            if retry_count < max_retries:
                time.sleep(2**retry_count)
                continue
            else:
                break

    # All retries exhausted
    log_entry.error_message = (
        f"Wszystkie proby nieudane ({max_retries}x): {str(last_error)}"
    )
    log_entry.save()
    return "error", log_entry


def process_single_publication(publication, pbn_client, task, log_model):
    """
    Process a single publication for sending statements to PBN.

    Args:
        publication: Publication instance to process
        pbn_client: PBN API client
        task: PbnWysylkaOswiadczenTask instance
        log_model: PbnWysylkaLog model class

    Returns:
        tuple: (status, log_entry)
    """
    content_type = ContentType.objects.get_for_model(publication)
    pbn_uid = str(publication.pbn_uid_id) if publication.pbn_uid_id else ""

    # Create log entry
    log_entry = log_model(
        task=task,
        content_type=content_type,
        object_id=publication.pk,
        pbn_uid=pbn_uid,
        status="error",  # Default to error, will update on success
    )

    # Step 1: Always delete existing statements
    _delete_existing_statements(publication, pbn_client, log_entry)

    # Step 2: Check if any autor has przypieta=True
    has_przypiete = publication.autorzy_set.filter(
        przypieta=True, dyscyplina_naukowa__isnull=False
    ).exists()

    if not has_przypiete:
        # No przypiete statements to send - mark as skipped
        log_entry.status = "skipped"
        log_entry.error_message = "Brak autorow z przypieta dyscyplina"
        log_entry.save()
        return "skipped", log_entry

    # Step 3: Get statements data
    try:
        json_data = WydawnictwoPBNAdapter(publication).pbn_get_api_statements()
    except DaneLokalneWymagajaAktualizacjiException as e:
        log_entry.error_message = f"Dane lokalne wymagaja aktualizacji: {str(e)}"
        log_entry.save()
        return "error", log_entry

    if not json_data:
        # No data to send
        log_entry.status = "skipped"
        log_entry.error_message = "Brak danych do wyslania"
        log_entry.save()
        return "skipped", log_entry

    log_entry.json_sent = json_data

    # Step 4: Send statements with retry
    return _send_statements_with_retry(pbn_client, json_data, log_entry)


@shared_task(bind=True)
def wysylka_oswiadczen_task(self, task_id: int):
    """
    Main Celery task for sending statements to PBN.

    Process:
    1. Get task record, mark as running
    2. Build publication list based on task parameters
    3. If resume_mode, skip publications already successfully processed
    4. For each publication: delete statements, send if przypiete, log result
    5. Mark task as completed
    """
    from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask

    try:
        task = PbnWysylkaOswiadczenTask.objects.get(pk=task_id)
    except PbnWysylkaOswiadczenTask.DoesNotExist:
        return {"error": f"Task {task_id} not found"}

    # Mark as running
    task.status = "running"
    task.started_at = timezone.now()
    task.celery_task_id = self.request.id
    task.save()

    try:
        # Get PBN client
        pbn_client = get_pbn_client(task.user)

        # Build publication list
        ciagle_qs, zwarte_qs = get_publications_queryset(
            task.rok_od, task.rok_do, task.tytul or None
        )
        combined_qs = QuerySetSequence(ciagle_qs, zwarte_qs)
        publications = list(combined_qs)

        task.total_publications = len(publications)
        task.save()

        # If resume mode, get already processed publications
        already_processed_pbn_uids = set()
        if task.resume_mode:
            # Get PBN UIDs from all successful logs (from all previous tasks)
            already_processed_pbn_uids = set(
                PbnWysylkaLog.objects.filter(status="success").values_list(
                    "pbn_uid", flat=True
                )
            )

        # Process publications
        for idx, publication in enumerate(publications, 1):
            pbn_uid = str(publication.pbn_uid_id) if publication.pbn_uid_id else ""

            # Update progress
            title_short = (publication.tytul_oryginalny or "")[:50]
            task.current_publication = f"{publication.pk}: {title_short}"
            task.processed_publications = idx

            # Check if already processed in resume mode
            if task.resume_mode and pbn_uid in already_processed_pbn_uids:
                task.skipped_count += 1
                task.save()
                continue

            # Process publication
            status, log_entry = process_single_publication(
                publication, pbn_client, task, PbnWysylkaLog
            )

            # Update counters
            if status == "success":
                task.success_count += 1
            elif status == "error":
                task.error_count += 1
            else:  # skipped
                task.skipped_count += 1

            # Save progress periodically (every 10 publications)
            if idx % 10 == 0:
                task.save()

        # Mark as completed
        task.status = "completed"
        task.completed_at = timezone.now()
        task.current_publication = ""
        task.save()

        return {
            "success": True,
            "total": task.total_publications,
            "processed": task.processed_publications,
            "success_count": task.success_count,
            "error_count": task.error_count,
            "skipped_count": task.skipped_count,
        }

    except PraceSerwisoweException:
        task.status = "maintenance"
        task.error_message = (
            "Prace serwisowe w PBN. Proszę spróbować ponownie za kilka godzin."
        )
        task.completed_at = timezone.now()
        task.save()
        return {"error": "prace_serwisowe", "message": task.error_message}

    except Exception as e:
        task.status = "failed"
        task.error_message = f"{str(e)}\n\n{traceback.format_exc()}"
        task.completed_at = timezone.now()
        task.save()

        return {"error": str(e)}
