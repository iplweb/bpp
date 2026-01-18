"""Main import manager that orchestrates the entire import process"""

import logging
import sys
import traceback
from typing import Any

import rollbar
from django.core.management import call_command
from django.utils import timezone

from ..models import ImportLog, ImportSession
from .base import CancelledException
from .step_definitions import get_step_definitions

logger = logging.getLogger("pbn_import")


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

        # Define import steps with their order
        self.steps = get_step_definitions(self.config)

        # Check PBN authorization status
        self._check_pbn_authorization()

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

    def _has_error_logs(self) -> bool:
        """Check if there are any error or critical log entries for this session"""
        return ImportLog.objects.filter(
            session=self.session, level__in=["error", "critical"]
        ).exists()

    def _refresh_pbn_client_after_setup(self):
        """Refresh PBN client after initial setup changes configuration.

        On a clean database, pbn_uid_id may be None when the import starts.
        InitialSetup may set it, but the original PBN client won't have this
        configuration. This method refreshes the client after InitialSetup
        to ensure proper authorization for subsequent API calls.
        """
        from bpp.models import Uczelnia

        # Refresh uczelnia from database to get changes made by InitialSetup
        uczelnia = Uczelnia.objects.get_default()

        if uczelnia is None:
            logger.warning("Nie znaleziono uczelni po InitialSetup")
            return

        # Log if pbn_uid_id is now set
        if uczelnia.pbn_uid_id:
            logger.info(f"Uczelnia ma PBN UID: {uczelnia.pbn_uid_id}")
            self.session.config["uczelnia_pbn_uid"] = uczelnia.pbn_uid_id
            self.session.save()

        # Get user token and recreate client
        pbn_token = getattr(self.session.user, "pbn_token", None)

        if pbn_token and uczelnia.pbn_integracja:
            try:
                new_client = uczelnia.pbn_client(pbn_token)
                self.client = new_client
                logger.info("Odświeżono klienta PBN po konfiguracji początkowej")

                # Re-check authorization with the new client
                self._check_pbn_authorization()

            except Exception as e:
                logger.warning(f"Nie udało się odświeżyć klienta PBN: {e}")

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

        # Aktualizuj last_updated aby zaznaczyć że zadanie nadal działa
        self.session.save(update_fields=["last_updated"])

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
            f">>> Uruchamianie etapu {idx + 1}/{len(self.steps)}: "
            f"{step_config['display']}"
        )

        try:
            result = step()
            results[step_config["name"]] = result

            # After initial_setup, refresh the client and authorization
            # This is critical for clean database imports where pbn_uid_id
            # gets set by InitialSetup after the client was created
            if step_config["name"] == "initial_setup":
                self._refresh_pbn_client_after_setup()

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

        # Check if there are error logs even if no step raised an exception
        if not has_errors and self._has_error_logs():
            has_errors = True
            if not critical_error:
                # Get first error as the message
                first_error = (
                    ImportLog.objects.filter(
                        session=self.session, level__in=["error", "critical"]
                    )
                    .order_by("timestamp")
                    .first()
                )
                if first_error:
                    critical_error = first_error.message

        logger.info("=" * 60)
        logger.info("IMPORT PBN - ZAKOŃCZONY")

        if has_errors:
            error_message = critical_error or "Import zakończony z błędami"
            tb_string = tb_string if "tb_string" in locals() else ""
            self.session.mark_failed(error_message, tb_string)
            logger.info("Status: BŁĘDY")
            logger.info("=" * 60)
            return {
                "success": False,
                "results": results,
                "message": f"Import zakończony z błędami: {error_message}",
            }
        else:
            self.session.mark_completed()
            logger.info("Status: SUKCES")
            logger.info("=" * 60)
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

            # Check for error logs after each step - stop if errors occurred
            if self._has_error_logs():
                first_error = (
                    ImportLog.objects.filter(
                        session=self.session, level__in=["error", "critical"]
                    )
                    .order_by("timestamp")
                    .first()
                )
                if first_error:
                    critical_error = first_error.message
                    has_errors = True
                    logger.warning(
                        f"Przerywanie importu z powodu błędu w kroku "
                        f"{step_config['name']}: {critical_error}"
                    )
                    ImportLog.objects.create(
                        session=self.session,
                        level="warning",
                        step="Import Control",
                        message=f"Import zatrzymany z powodu błędu: {critical_error}",
                    )
                    break

        return has_errors, critical_error, tb_string, False, None

    def run(self):
        """Execute the complete import process"""
        logger.info("=" * 60)
        logger.info("IMPORT PBN - START")
        logger.info(f"Sesja: {self.session.id}")
        logger.info(f"Etapy do wykonania: {len(self.steps)}")
        logger.info("=" * 60)

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
