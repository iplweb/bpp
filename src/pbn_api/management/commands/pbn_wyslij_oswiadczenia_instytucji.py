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
import traceback

from django.core.management.base import CommandError
from queryset_sequence import QuerySetSequence
from tqdm import tqdm

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    DaneLokalneWymagajaAktualizacjiException,
    HttpException,
)
from pbn_api.management.commands.util import PBNBaseCommand

from django.contrib.contenttypes.models import ContentType

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


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

    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        publication_id = options.get("publication_id")
        year = options.get("year")
        dry_run = options["dry_run"]

        pbn_client = self.get_client(app_id, app_token, base_url, user_token)

        # Validate arguments
        if not publication_id and not year:
            raise CommandError("Either publication_id or --year must be provided")

        if publication_id and year:
            raise CommandError("Cannot specify both publication_id and --year")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No data will be sent to PBN")
            )

        if publication_id:
            # Single publication mode
            publication = self._get_single_publication(publication_id)
            publications = [publication]
        else:
            # Batch processing mode
            publications = self._get_publications_by_year(year)

        if not publications:
            self.stdout.write(self.style.WARNING("No publications found to process"))
            return

        for publication in tqdm(publications, desc="Wysyłam oświadczenia"):
            try:
                json_data = WydawnictwoPBNAdapter(publication).pbn_get_api_statements()
            except DaneLokalneWymagajaAktualizacjiException as e:
                self.stdout.write(self.style.ERROR(str(e)))
                continue

            if not json_data:
                continue

            # json_data["publicationUuid"] = "275da353-ddad-4234-b456-71af3b417ac6"
            try:
                if dry_run:
                    print(f"// wysyłam: publikacja {publication}")
                    print(f"// BPP ID {publication.pk}")
                    print(json.dumps(json_data, indent=2))
                else:
                    try:
                        pbn_client.delete_all_publication_statements(
                            publication.pbn_uid_id
                        )
                        time.sleep(0.5)
                    except CannotDeleteStatementsException:
                        pass

                    max_tries = 5
                    while max_tries > 0:
                        max_tries -= 1

                        try:
                            pbn_client.post_discipline_statements({"data": [json_data]})
                            break
                        except HttpException as e:
                            if e.status_code == 500:

                                #
                                # Problem, PBN?
                                #
                                # ⠀⠀⠀⠀⠀⠀⢀⣤⠤⠤⠤⠤⠤⠤⠤⠤⠤⠤⢤⣤⣀⣀⡀⠀⠀⠀⠀⠀⠀
                                # ⠀⠀⠀⠀⢀⡼⠋⠀⣀⠄⡂⠍⣀⣒⣒⠂⠀⠬⠤⠤⠬⠍⠉⠝⠲⣄⡀⠀⠀
                                # ⠀⠀⠀⢀⡾⠁⠀⠊⢔⠕⠈⣀⣀⡀⠈⠆⠀⠀⠀⡍⠁⠀⠁⢂⠀⠈⣷⠀⠀
                                # ⠀⠀⣠⣾⠥⠀⠀⣠⢠⣞⣿⣿⣿⣉⠳⣄⠀⠀⣀⣤⣶⣶⣶⡄⠀⠀⣘⢦⡀
                                # ⢀⡞⡍⣠⠞⢋⡛⠶⠤⣤⠴⠚⠀⠈⠙⠁⠀⠀⢹⡏⠁⠀⣀⣠⠤⢤⡕⠱⣷
                                # ⠘⡇⠇⣯⠤⢾⡙⠲⢤⣀⡀⠤⠀⢲⡖⣂⣀⠀⠀⢙⣶⣄⠈⠉⣸⡄⠠⣠⡿
                                # ⠀⠹⣜⡪⠀⠈⢷⣦⣬⣏⠉⠛⠲⣮⣧⣁⣀⣀⠶⠞⢁⣀⣨⢶⢿⣧⠉⡼⠁
                                # ⠀⠀⠈⢷⡀⠀⠀⠳⣌⡟⠻⠷⣶⣧⣀⣀⣹⣉⣉⣿⣉⣉⣇⣼⣾⣿⠀⡇⠀
                                # ⠀⠀⠀⠈⢳⡄⠀⠀⠘⠳⣄⡀⡼⠈⠉⠛⡿⠿⠿⡿⠿⣿⢿⣿⣿⡇⠀⡇⠀
                                # ⠀⠀⠀⠀⠀⠙⢦⣕⠠⣒⠌⡙⠓⠶⠤⣤⣧⣀⣸⣇⣴⣧⠾⠾⠋⠀⠀⡇⠀
                                # ⠀⠀⠀⠀⠀⠀⠀⠈⠙⠶⣭⣒⠩⠖⢠⣤⠄⠀⠀⠀⠀⠀⠠⠔⠁⡰⠀⣧⠀
                                # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠲⢤⣀⣀⠉⠉⠀⠀⠀⠀⠀⠁⠀⣠⠏⠀
                                # ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠉⠛⠒⠲⠶⠤⠴⠒⠚⠁⠀⠀
                                time.sleep(1)
                                continue

                            if (
                                e.status_code == 423
                                and "Oświadczenie zostało zablokowane z uwagi na równoległą operację. "
                                "Prosimy spróbować ponownie." in e.content
                            ):
                                time.sleep(1)
                                continue

                            raise e

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing {publication}: {e}")
                )

                self.stdout.write(traceback.format_exc())

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
