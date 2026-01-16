"""Main import manager that orchestrates the entire import process"""

import logging
import sys
import traceback
from typing import Any

import rollbar
from django.core.management import call_command
from django.utils import timezone

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

logger = logging.getLogger(__name__)


class ImportManager:
    """Orchestrates the entire PBN import process"""

    def __init__(
        self, session: ImportSession, client, config: dict[str, Any] | None = None
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

    def _add_step_if_enabled(self, steps, config_key, step_def):
        """Add step to list if not disabled in config"""
        if not self.config.get(config_key):
            steps.append(step_def)

    def _initialize_steps(self) -> list[dict[str, Any]]:
        """Initialize and return list of import steps"""
        steps = []

        self._add_step_if_enabled(
            steps,
            "disable_initial",
            {
                "name": "initial_setup",
                "display": "Konfiguracja początkowa",
                "class": InitialSetup,
                "args": {},
                "required": True,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_institutions",
            {
                "name": "institution_setup",
                "display": "Konfiguracja jednostek",
                "class": InstitutionImporter,
                "args": {
                    "wydzial_domyslny": self.config.get(
                        "wydzial_domyslny", "Wydział Domyślny"
                    ),
                    "wydzial_domyslny_skrot": self.config.get("wydzial_domyslny_skrot"),
                },
                "required": True,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_zrodla",
            {
                "name": "source_import",
                "display": "Import źródeł",
                "class": SourceImporter,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_wydawcy",
            {
                "name": "publisher_import",
                "display": "Import wydawców",
                "class": PublisherImporter,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_konferencje",
            {
                "name": "conference_import",
                "display": "Import konferencji",
                "class": ConferenceImporter,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_autorzy",
            {
                "name": "author_import",
                "display": "Import autorów",
                "class": AuthorImporter,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_publikacje",
            {
                "name": "publication_import",
                "display": "Import publikacji",
                "class": PublicationImporter,
                "args": {
                    "delete_existing": self.config.get("delete_existing", False),
                },
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_integracja",
            {
                "name": "data_integration",
                "display": "Integruj nowe dane",
                "class": DataIntegrator,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_oswiadczenia",
            {
                "name": "statement_import",
                "display": "Import oświadczeń",
                "class": StatementImporter,
                "args": {},
                "required": False,
            },
        )

        self._add_step_if_enabled(
            steps,
            "disable_oplaty",
            {
                "name": "fee_import",
                "display": "Import opłat",
                "class": FeeImporter,
                "args": {},
                "required": False,
            },
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

    def _validate_pbn_authorization(self):
        """Validate PBN authorization before starting import"""
        needs_pbn = any(
            step["name"] not in ["initial_setup", "institution_setup"]
            for step in self.steps
        )

        if needs_pbn and not self.pbn_authorized:
            error_msg = self.pbn_error_message or "Import wymaga autoryzacji PBN"
            ImportLog.objects.create(
                session=self.session,
                level="critical",
                step="Authorization Check",
                message=error_msg,
            )
            raise Exception(error_msg)

    def _check_cancellation(self, results):
        """Check if import was cancelled and return early if so"""
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
        return None

    def _should_skip_step(self, step_config, results):
        """Check if step should be skipped due to PBN auth"""
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
            return True
        return False

    def _handle_step_error(
        self, e, step_config, results, has_errors, critical_error, tb_string
    ):
        """Handle errors that occur during step execution"""
        error_msg = self._extract_error_message(e)
        logger.error(f"Krok {step_config['name']} nie powiódł się: {error_msg}")

        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={
                "step": step_config["name"],
                "session_id": self.session.id,
                "required": step_config.get("required", False),
                "layer": "ImportManager",
            },
        )

        tb_string = traceback.format_exc()

        if hasattr(e, "content") or "403" in str(e) or "Forbidden" in error_msg:
            has_errors = True
            critical_error = error_msg
            results[step_config["name"]] = {
                "error": error_msg,
                "skipped": False,
                "critical": True,
            }
            return has_errors, critical_error, tb_string, True, None

        if step_config.get("required"):
            has_errors = True
            critical_error = error_msg
            return has_errors, critical_error, tb_string, False, None

        has_errors = True
        results[step_config["name"]] = {
            "error": error_msg,
            "skipped": False,
        }
        return has_errors, critical_error, tb_string, False, None

    def _execute_step(
        self, idx, step_config, results, has_errors, critical_error, tb_string
    ):
        """Execute a single import step"""
        step_class = step_config["class"]
        step = step_class(
            session=self.session, client=self.client, **step_config["args"]
        )

        logger.info(
            f"Uruchamianie kroku {idx + 1}/{len(self.steps)}: {step_config['display']}"
        )

        try:
            result = step()
            results[step_config["name"]] = result
            return has_errors, critical_error, tb_string, False, None

        except CancelledException:
            ImportLog.objects.create(
                session=self.session,
                level="warning",
                step=step_config["display"],
                message="Import został anulowany podczas wykonywania kroku",
            )
            logger.warning(
                f"Import {self.session.id} anulowany podczas kroku {step_config['name']}"
            )
            return (
                has_errors,
                critical_error,
                tb_string,
                False,
                {"success": False, "cancelled": True, "results": results},
            )

        except Exception as e:
            return self._handle_step_error(
                e, step_config, results, has_errors, critical_error, tb_string
            )

    def _finalize_import(self, results, has_errors, critical_error, tb_string):
        """Finalize the import process and return results"""
        if not critical_error:
            self._run_post_import_commands()

        if hasattr(self.session, "statistics"):
            self.session.statistics.calculate_coffee_breaks()
            self.session.statistics.save()

        if has_errors:
            error_message = critical_error or "Import zakończony z błędami"
            tb_string = tb_string if "tb_string" in locals() else ""
            self.session.mark_failed(error_message, tb_string)
            return {
                "success": False,
                "results": results,
                "message": f"Import zakończony z błędami: {error_message}",
            }
        else:
            self.session.mark_completed()
            return {
                "success": True,
                "results": results,
                "message": "Import zakończony pomyślnie",
            }

    def _run_import_steps(self, results):
        """Run all import steps and return status"""
        has_errors = False
        critical_error = None
        tb_string = None

        for idx, step_config in enumerate(self.steps):
            cancel_result = self._check_cancellation(results)
            if cancel_result:
                return (
                    has_errors,
                    critical_error,
                    tb_string,
                    True,
                    cancel_result,
                )

            self.session.completed_steps = idx
            self.session.save()

            if self._should_skip_step(step_config, results):
                has_errors = True
                continue

            (
                has_errors,
                critical_error,
                tb_string,
                should_break,
                cancel_result,
            ) = self._execute_step(
                idx, step_config, results, has_errors, critical_error, tb_string
            )

            if cancel_result:
                return (
                    has_errors,
                    critical_error,
                    tb_string,
                    True,
                    cancel_result,
                )

            if should_break:
                break

        return has_errors, critical_error, tb_string, False, None

    def run(self):
        """Execute the complete import process"""
        self.session.status = "running"
        self.session.total_steps = len(self.steps)
        self.session.save()

        results = {}
        has_errors = False
        critical_error = None

        try:
            self._validate_pbn_authorization()

            (
                has_errors,
                critical_error,
                tb_string,
                should_cancel,
                cancel_result,
            ) = self._run_import_steps(results)

            if should_cancel:
                return cancel_result

            return self._finalize_import(results, has_errors, critical_error, tb_string)

        except Exception as e:
            return self._handle_critical_error(e)

    def _handle_critical_error(self, e):
        """Handle critical errors during import"""
        logger.error(f"Import nie powiódł się: {e}")

        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={
                "session_id": self.session.id,
                "error_type": "critical_import_failure",
            },
        )

        tb_string = traceback.format_exc()
        self.session.mark_failed(str(e), tb_string)
        return {
            "success": False,
            "error": str(e),
            "traceback": tb_string,
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
