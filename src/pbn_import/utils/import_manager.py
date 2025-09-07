"""Main import manager that orchestrates the entire import process"""

import logging
from typing import Any, Dict, List, Optional

from django.core.management import call_command

from ..models import ImportLog, ImportSession, ImportStatistics, ImportStep
from .author_import import AuthorImporter
from .base import CancelledException
from .conference_import import ConferenceImporter
from .data_integration import DataIntegrator
from .fee_import import FeeImporter
from .initial_setup import InitialSetup
from .institution_import import InstitutionImporter
from .publication_import import PublicationImporter
from .publisher_import import PublisherImporter
from .source_import import SourceImporter
from .statement_import import StatementImporter

from django.utils import timezone

logger = logging.getLogger(__name__)


class ImportManager:
    """Orchestrates the entire PBN import process"""

    def __init__(
        self, session: ImportSession, client, config: Optional[Dict[str, Any]] = None
    ):
        self.session = session
        self.client = client
        self.config = config or {}
        self.pbn_authorized = False
        self.pbn_error_message = None

        # Store config in session
        self.session.config.update(self.config)
        self.session.save()

        # Create statistics object if doesn't exist
        if not hasattr(self.session, "statistics"):
            ImportStatistics.objects.get_or_create(session=self.session)

        # Define import steps with their order
        self.steps = self._initialize_steps()

        # Check PBN authorization status
        self._check_pbn_authorization()

    def _initialize_steps(self) -> List[Dict[str, Any]]:
        """Initialize and return list of import steps"""
        steps = []

        # Initial setup (always required)
        if not self.config.get("disable_initial"):
            steps.append(
                {
                    "name": "initial_setup",
                    "display": "Konfiguracja początkowa",
                    "class": InitialSetup,
                    "args": {},
                    "required": True,
                }
            )

        # Institution setup
        if not self.config.get("disable_institutions"):
            steps.append(
                {
                    "name": "institution_setup",
                    "display": "Konfiguracja jednostek",
                    "class": InstitutionImporter,
                    "args": {
                        "wydzial_domyslny": self.config.get(
                            "wydzial_domyslny", "Wydział Domyślny"
                        ),
                        "wydzial_domyslny_skrot": self.config.get(
                            "wydzial_domyslny_skrot"
                        ),
                    },
                    "required": True,
                }
            )

        # Sources
        if not self.config.get("disable_zrodla"):
            steps.append(
                {
                    "name": "source_import",
                    "display": "Import źródeł",
                    "class": SourceImporter,
                    "args": {},
                    "required": False,
                }
            )

        # Publishers
        if not self.config.get("disable_wydawcy"):
            steps.append(
                {
                    "name": "publisher_import",
                    "display": "Import wydawców",
                    "class": PublisherImporter,
                    "args": {},
                    "required": False,
                }
            )

        # Conferences
        if not self.config.get("disable_konferencje"):
            steps.append(
                {
                    "name": "conference_import",
                    "display": "Import konferencji",
                    "class": ConferenceImporter,
                    "args": {},
                    "required": False,
                }
            )

        # Authors
        if not self.config.get("disable_autorzy"):
            steps.append(
                {
                    "name": "author_import",
                    "display": "Import autorów",
                    "class": AuthorImporter,
                    "args": {},
                    "required": False,
                }
            )

        # Publications
        if not self.config.get("disable_publikacje"):
            steps.append(
                {
                    "name": "publication_import",
                    "display": "Import publikacji",
                    "class": PublicationImporter,
                    "args": {
                        "delete_existing": self.config.get("delete_existing", False),
                    },
                    "required": False,
                }
            )

        # Data Integration - integrate new data after publication import
        if not self.config.get("disable_integracja"):
            steps.append(
                {
                    "name": "data_integration",
                    "display": "Integruj nowe dane",
                    "class": DataIntegrator,
                    "args": {},
                    "required": False,
                }
            )

        # Statements
        if not self.config.get("disable_oswiadczenia"):
            steps.append(
                {
                    "name": "statement_import",
                    "display": "Import oświadczeń",
                    "class": StatementImporter,
                    "args": {},
                    "required": False,
                }
            )

        # Fees
        if not self.config.get("disable_oplaty"):
            steps.append(
                {
                    "name": "fee_import",
                    "display": "Import opłat",
                    "class": FeeImporter,
                    "args": {},
                    "required": False,
                }
            )

        return steps

    def create_import_steps(self):
        """Create ImportStep records in database"""
        for idx, step in enumerate(self.steps):
            ImportStep.objects.get_or_create(
                name=step["name"],
                defaults={
                    "display_name": step["display"],
                    "order": idx * 10,
                    "is_optional": not step.get("required", False),
                    "estimated_duration": 60,  # Default 60 seconds
                    "icon_class": self._get_icon_for_step(step["name"]),
                },
            )

    def _get_icon_for_step(self, step_name: str) -> str:
        """Get Foundation icon class for step"""
        icons = {
            "initial_setup": "fi-wrench",
            "institution_setup": "fi-home",
            "source_import": "fi-book",
            "publisher_import": "fi-page-multiple",
            "conference_import": "fi-calendar",
            "author_import": "fi-torsos-all",
            "publication_import": "fi-page-copy",
            "data_integration": "fi-link",
            "statement_import": "fi-clipboard-pencil",
            "fee_import": "fi-dollar",
        }
        return icons.get(step_name, "fi-download")

    def _check_pbn_authorization(self):
        """Check if PBN client is properly authorized"""
        if self.client is None:
            logger.warning("Brak klienta PBN - niektóre importy mogą nie działać")
            self.pbn_authorized = False
            self.pbn_error_message = "Brak konfiguracji klienta PBN"
            return

        try:
            # Try to make a simple API call to check authorization
            # The get_languages call will trigger authorization check
            self.client.get_languages()
            self.pbn_authorized = True
            logger.info("Autoryzacja PBN potwierdzona")
        except Exception as e:
            self.pbn_authorized = False
            self.pbn_error_message = self._extract_error_message(e)
            logger.error(f"Błąd PBN: {self.pbn_error_message}")

    def _extract_error_message(self, exception):
        """Extract meaningful error message from PBN API exception"""
        import json

        # Check if it's an AccessDeniedException with content
        if hasattr(exception, "content"):
            try:
                # Try to parse as JSON
                if isinstance(exception.content, str):
                    error_data = json.loads(exception.content)
                else:
                    error_data = json.loads(exception.content.decode("utf-8"))

                # Extract description if available
                if "description" in error_data:
                    return error_data["description"]
                elif "message" in error_data:
                    return error_data["message"]
            except (json.JSONDecodeError, AttributeError):
                # If not JSON, return raw content
                if isinstance(exception.content, str):
                    return exception.content
                else:
                    return str(exception.content)

        # Fallback to string representation
        return str(exception)

    def run(self):
        """Execute the complete import process"""
        self.session.status = "running"
        self.session.total_steps = len(self.steps)
        self.session.save()

        results = {}
        has_errors = False
        critical_error = None

        try:
            # Check if we need PBN authorization for any steps
            needs_pbn = any(
                step["name"] not in ["initial_setup", "institution_setup"]
                for step in self.steps
            )

            if needs_pbn and not self.pbn_authorized:
                # If we need PBN but don't have authorization, fail immediately
                # Use the actual error message from the API
                error_msg = self.pbn_error_message or "Import wymaga autoryzacji PBN"
                # Log this critical error
                ImportLog.objects.create(
                    session=self.session,
                    level="critical",
                    step="Authorization Check",
                    message=error_msg,
                )
                raise Exception(error_msg)

            for idx, step_config in enumerate(self.steps):
                # Check if import was cancelled
                self.session.refresh_from_db()
                if self.session.status == "cancelled":
                    ImportLog.objects.create(
                        session=self.session,
                        level="warning",
                        step="Cancellation",
                        message="Import został anulowany przez użytkownika",
                    )
                    logger.warning(f"Import {self.session.id} został anulowany")
                    return {"success": False, "cancelled": True, "results": results}

                self.session.completed_steps = idx
                self.session.save()

                # Skip PBN-dependent steps if not authorized
                if not self.pbn_authorized and step_config["name"] not in [
                    "initial_setup",
                    "institution_setup",
                ]:
                    logger.warning(
                        f"Pomijanie kroku {step_config['display']} - brak autoryzacji PBN"
                    )
                    results[step_config["name"]] = {
                        "error": "Brak autoryzacji PBN",
                        "skipped": True,
                    }
                    has_errors = True
                    continue

                # Create and run step
                step_class = step_config["class"]
                step = step_class(
                    session=self.session, client=self.client, **step_config["args"]
                )

                logger.info(
                    f"Uruchamianie kroku {idx+1}/{len(self.steps)}: {step_config['display']}"
                )

                try:
                    result = step()
                    results[step_config["name"]] = result

                except CancelledException:
                    # Import was cancelled during step execution
                    ImportLog.objects.create(
                        session=self.session,
                        level="warning",
                        step=step_config["display"],
                        message="Import został anulowany podczas wykonywania kroku",
                    )
                    logger.warning(
                        f"Import {self.session.id} anulowany podczas kroku {step_config['name']}"
                    )
                    return {"success": False, "cancelled": True, "results": results}

                except Exception as e:
                    error_msg = self._extract_error_message(e)
                    logger.error(
                        f"Krok {step_config['name']} nie powiódł się: {error_msg}"
                    )

                    # Check if it's an authorization/access error
                    # The error message from API will be more descriptive
                    if (
                        hasattr(e, "content")
                        or "403" in str(e)
                        or "Forbidden" in error_msg
                    ):
                        has_errors = True
                        critical_error = error_msg
                        results[step_config["name"]] = {
                            "error": error_msg,
                            "skipped": False,
                            "critical": True,
                        }
                        # Stop processing further steps
                        break

                    if step_config.get("required"):
                        # Required step failed - abort
                        has_errors = True
                        critical_error = error_msg
                        raise
                    else:
                        # Optional step failed - continue but mark as having errors
                        has_errors = True
                        results[step_config["name"]] = {
                            "error": error_msg,
                            "skipped": False,
                        }

            # Only run post-import commands if no critical errors
            if not critical_error:
                self._run_post_import_commands()

            # Calculate fun statistics
            if hasattr(self.session, "statistics"):
                self.session.statistics.calculate_coffee_breaks()
                self.session.statistics.save()

            # If we had any errors, mark as failed
            if has_errors:
                error_message = critical_error or "Import zakończony z błędami"
                self.session.mark_failed(error_message)
                return {
                    "success": False,
                    "results": results,
                    "message": f"Import zakończony z błędami: {error_message}",
                }
            else:
                # Mark session as completed only if no errors
                self.session.mark_completed()
                return {
                    "success": True,
                    "results": results,
                    "message": "Import zakończony pomyślnie",
                }

        except Exception as e:
            logger.error(f"Import nie powiódł się: {e}")
            self.session.mark_failed(str(e))
            return {
                "success": False,
                "error": str(e),
                "message": f"Import nie powiódł się: {str(e)}",
            }

    def _run_post_import_commands(self):
        """Run Django management commands after import"""
        commands = [
            (
                "ustaw_zwrotnie_punkty_zwartych",
                "Ustawianie punktów publikacji zwartych",
            ),
            (
                "ustaw_zwrotnie_punkty_ciaglych",
                "Ustawianie punktów publikacji ciągłych",
            ),
            (
                "przypisz_rekordy_aktualnym_jednostkom_autorow",
                "Przypisywanie rekordów do jednostek",
            ),
            ("denorm_flush", "Odświeżanie denormalizacji"),
        ]

        for cmd, description in commands:
            try:
                self.session.current_step = description
                self.session.save()

                logger.info(f"Uruchamianie komendy: {cmd}")
                call_command(cmd)

            except Exception as e:
                logger.error(f"Komenda {cmd} nie powiodła się: {e}")
                # Don't fail the entire import for post-processing errors

    def pause(self):
        """Pause the import process"""
        self.session.status = "paused"
        self.session.save()

    def resume(self):
        """Resume the import process"""
        self.session.status = "running"
        self.session.save()

    def cancel(self):
        """Cancel the import process"""
        self.session.status = "cancelled"
        self.session.completed_at = timezone.now()
        self.session.save()
