#!/usr/bin/env python3

"""
Wysyła wyłącznie dane oświadczeń do PBN API

Usage:
    # Single publication:
    python manage.py pbn_send_statements <publication_id> [--dry-run]

    # Batch processing by year:
    python manage.py pbn_send_statements --year <year> [--dry-run]

Examples:
    python manage.py pbn_send_statements wydawnictwo_ciagle:123
    python manage.py pbn_send_statements wydawnictwo_zwarte:456 --dry-run
    python manage.py pbn_send_statements --year 2023
    python manage.py pbn_send_statements --year 2022 --dry-run
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError
from queryset_sequence import QuerySetSequence
from tqdm import tqdm

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    DaneLokalneWymagajaAktualizacjiException,
    HttpException,
)
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import PublikacjaInstytucji_V2, Scientist


def post_discipline_statements_error_handler(json_response):
    """
    Parse JSON response from PBN API and convert UUIDs and IDs to model instances.

    Args:
        json_response (dict): JSON response from PBN API with format:
        {
            "data": [
                {
                    "publicationUuid": "8b25d071-6fbb-45ce-9082-65be455dcbb4",
                    "statements": [
                        {
                            "status": "IGNORED|INVALID",
                            "personObjectId": "5e709224878c28a0473908ed",
                            "personRole": "AUTHOR",
                            "statementErrors": [
                                {
                                    "code": "PERSON_NOT_IN_PUBLICATION",
                                    "description": "Wskazana osoba nie pełni podanej roli w publikacji."
                                }
                            ]
                        }
                    ]
                }
            ]
        }

    Returns:
        list: List of parsed publication data with resolved model instances
    """
    parsed_data = []

    if not json_response or "data" not in json_response:
        return parsed_data

    for publication_data in json_response["data"]:
        publication_uuid = publication_data.get("publicationUuid")
        statements = publication_data.get("statements", [])

        # Resolve publication instance
        publikacja_instytucji = None
        if publication_uuid:
            try:
                publikacja_instytucji = PublikacjaInstytucji_V2.objects.get(
                    uuid=publication_uuid
                )
            except PublikacjaInstytucji_V2.DoesNotExist:
                # Publication not found in local database
                pass

        parsed_statements = []
        for statement in statements:
            person_object_id = statement.get("personObjectId")
            status = statement.get("status")
            person_role = statement.get("personRole")
            statement_errors = statement.get("statementErrors", [])

            # Resolve scientist instance
            scientist = None
            if person_object_id:
                try:
                    scientist = Scientist.objects.get(mongoId=person_object_id)
                except Scientist.DoesNotExist:
                    # Scientist not found in local database
                    pass

            parsed_statement = {
                "raw_person_object_id": person_object_id,
                "scientist": scientist,
                "status": status,
                "person_role": person_role,
                "statement_errors": statement_errors,
                "has_errors": status == "INVALID" and len(statement_errors) > 0,
                "should_ignore": status == "IGNORED",
            }

            parsed_statements.append(parsed_statement)

        parsed_publication = {
            "raw_publication_uuid": publication_uuid,
            "publikacja_instytucji": publikacja_instytucji,
            "statements": parsed_statements,
            "has_any_errors": any(stmt["has_errors"] for stmt in parsed_statements),
            "error_count": sum(1 for stmt in parsed_statements if stmt["has_errors"]),
        }

        parsed_data.append(parsed_publication)

    return parsed_data


def process_single_publication(
    publication: Wydawnictwo_Ciagle | Wydawnictwo_Ciagle,
    pbn_client,
    dry_run=False,
    progress_lock=None,
    stdout=None,
    style=None,
):
    """
    Process a single publication for sending statements to PBN.

    Args:
        publication: Publication instance to process
        pbn_client: PBN API client
        dry_run: If True, only show what would be sent
        progress_lock: Threading lock for thread-safe output
        stdout: Command stdout for output
        style: Command style for colored output

    Returns:
        dict: Result of processing with success/error information
    """
    result = {
        "publication": publication,
        "success": False,
        "error": None,
        "json_data": None,
    }

    try:
        json_data = WydawnictwoPBNAdapter(publication).pbn_get_api_statements()
        result["json_data"] = json_data

    except DaneLokalneWymagajaAktualizacjiException as e:
        result["error"] = str(e)
        if stdout and style and progress_lock:
            with progress_lock:
                tqdm.write(
                    style.ERROR(f"{publication.pk};{publication.tytul_oryginalny};{e}")
                )
        return result

    if not json_data:
        result["success"] = True  # No data to send is considered success
        return result

    try:
        if dry_run:
            if stdout and progress_lock:
                with progress_lock:
                    tqdm.write(f"// wysyłam: publikacja {publication}")
                    tqdm.write(f"// BPP ID {publication.pk}")
                    tqdm.write(json.dumps(json_data, indent=2))
            result["success"] = True
        else:
            try:
                pbn_client.delete_all_publication_statements(publication.pbn_uid_id)
                time.sleep(0.5)
            except CannotDeleteStatementsException:
                # Skoro nie można usunąć to PRAWDOPODOBNIE ich tam po prostu nie ma.
                pass

            max_tries = 5
            while max_tries > 0:
                max_tries -= 1

                try:
                    pbn_client.post_discipline_statements({"data": [json_data]})
                    result["success"] = True
                    break
                except HttpException as e:
                    if e.status_code == 500:
                        time.sleep(1)
                        continue

                    if e.status_code == 400:
                        try:
                            error_json = json.loads(e.content)
                        except json.decoder.JSONDecodeError:
                            raise e

                        res = post_discipline_statements_error_handler(error_json)
                        # Store parsed errors in result for potential debugging
                        result["parsed_errors"] = res
                        raise e

                    if (
                        e.status_code == 423
                        and "Oświadczenie zostało zablokowane z uwagi na równoległą operację. "
                        "Prosimy spróbować ponownie."
                        in e.content
                    ):
                        time.sleep(1)
                        continue

                    raise e

    except Exception as e:
        result["error"] = str(e)
        if stdout and style and progress_lock:
            with progress_lock:
                tqdm.write(
                    style.ERROR(f"{publication.pk};{publication.tytul_oryginalny};{e}")
                )
                # tqdm.write(traceback.format_exc())

    return result


class Command(PBNBaseCommand):
    help = "Send discipline statements to PBN API for publications (single or batch by year)"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "publication_id",
            type=str,
            nargs="?",
            help="Publication ID in format 'model_name:pk' (e.g., 'wydawnictwo_ciagle:123')",
        )
        parser.add_argument(
            "--year",
            type=int,
            help="Process all publications from specified year",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending to PBN",
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=12,
            help="Number of threads to use for parallel processing (default: 12, max: 32)",
        )
        parser.add_argument(
            "--no-threads",
            action="store_true",
            help="Disable threading for debugging purposes",
        )

    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        publication_id = options.get("publication_id")
        year = options.get("year")
        dry_run = options["dry_run"]
        num_threads = max(
            1, min(32, options.get("threads", 12))
        )  # Clamp between 1 and 12
        no_threads = options.get("no_threads", False)

        if no_threads:
            num_threads = 1

        pbn_client = self.get_client(app_id, app_token, base_url, user_token)

        # Validate arguments
        if not publication_id and not year:
            raise CommandError("Either publication_id or --year must be provided")

        if publication_id and year:
            raise CommandError("Cannot specify both publication_id and --year")

        if dry_run:
            tqdm.write(self.style.WARNING("DRY RUN MODE - No data will be sent to PBN"))

        if num_threads > 1:
            tqdm.write(
                self.style.SUCCESS(
                    f"Using {num_threads} threads for parallel processing"
                )
            )
        else:
            tqdm.write(
                self.style.WARNING("Threading disabled - processing sequentially")
            )

        if publication_id:
            # Single publication mode
            try:
                publication = self._get_single_publication(publication_id)
            except CommandError:
                from bpp.models import Rekord

                publication = Rekord.objects.get(pbn_uid_id=publication_id).original
            publications = [publication]
        else:
            # Batch processing mode
            publications = self._get_publications_by_year(year)

        if not publications:
            tqdm.write(self.style.WARNING("No publications found to process"))
            return

        # Initialize progress tracking
        progress_lock = Lock()
        total_publications = (
            len(publications)
            if hasattr(publications, "__len__")
            else sum(1 for _ in publications)
        )

        success_count = 0
        error_count = 0

        if num_threads == 1 or no_threads:
            # Sequential processing for debugging
            for publication in tqdm(publications, desc="Wysyłam oświadczenia"):
                result = process_single_publication(
                    publication,
                    pbn_client,
                    dry_run,
                    progress_lock,
                    self.stdout,
                    self.style,
                )
                if result["success"]:
                    success_count += 1
                else:
                    error_count += 1
        else:
            # Parallel processing with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all tasks - each publication gets submitted exactly once
                future_to_publication = {
                    executor.submit(
                        process_single_publication,
                        publication,
                        pbn_client,
                        dry_run,
                        progress_lock,
                        self.stdout,
                        self.style,
                    ): publication
                    for publication in publications
                }

                tasks_submitted = len(future_to_publication)
                tqdm.write(
                    self.style.SUCCESS(
                        f"Submitted {tasks_submitted} tasks to {num_threads} worker threads"
                    )
                )

                # Process completed tasks with progress bar
                with tqdm(
                    total=total_publications, desc="Wysyłam oświadczenia"
                ) as pbar:
                    for future in as_completed(future_to_publication):
                        result = future.result()
                        if result["success"]:
                            success_count += 1
                        else:
                            error_count += 1
                        pbar.update(1)

        # Print final summary
        tqdm.write(
            self.style.SUCCESS(
                f"\nCompleted processing {success_count + error_count} publications"
            )
        )
        tqdm.write(self.style.SUCCESS(f"Successful: {success_count}"))
        if error_count > 0:
            tqdm.write(self.style.ERROR(f"Errors: {error_count}"))

    def _get_single_publication(self, publication_id):
        """Get a single publication by ID."""
        # Parse publication ID
        if ":" not in publication_id:
            raise CommandError(
                "Publication ID must be in format 'model_name:pk' "
                "(e.g., 'wydawnictwo_ciagle:123')"
            )

        model_name, pk = publication_id.split(":", 1)

        # Get the model class
        try:
            content_type = ContentType.objects.get(app_label="bpp", model=model_name)
            model_class = content_type.model_class()
        except ContentType.DoesNotExist:
            raise CommandError(f"Model '{model_name}' not found in BPP app")

        # Get the publication record
        try:
            publication = model_class.objects.get(pk=pk)
        except model_class.DoesNotExist:
            raise CommandError(f"Publication {model_name}:{pk} does not exist")

        # Check if publication has PBN UID
        if not hasattr(publication, "pbn_uid_id") or publication.pbn_uid_id is None:
            raise CommandError(
                f"Publication '{publication}' does not have a PBN UID. "
                "Cannot send statements."
            )

        return publication

    def _get_publications_by_year(self, year):
        """Get all publications (Wydawnictwo_Zwarte and Wydawnictwo_Ciagle) by year."""

        filter_kw = dict(
            rok=year,
            pbn_uid_id__isnull=False,
            autorzy_set__dyscyplina_naukowa__isnull=False,
        )
        # Get Wydawnictwo_Zwarte publications
        zwarte_qs = Wydawnictwo_Zwarte.objects.filter(**filter_kw).select_related(
            "pbn_uid"
        )

        # Get Wydawnictwo_Ciagle publications
        ciagle_qs = Wydawnictwo_Ciagle.objects.filter(**filter_kw).select_related(
            "pbn_uid"
        )

        # Use QuerySetSequence for memory efficiency
        return QuerySetSequence(zwarte_qs, ciagle_qs)
