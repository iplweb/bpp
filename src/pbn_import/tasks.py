"""Celery tasks for PBN import"""

import logging
import sys
import traceback

import rollbar
from celery import shared_task
from django.utils import timezone

from bpp.models import Uczelnia
from bpp.util import zaloguj_polkniety_wyjatek

from .models import ImportLog, ImportSession
from .utils import ImportManager

logger = logging.getLogger("pbn_import")


@shared_task(bind=True)
def run_pbn_import(self, session_id, uczelnia_id=None):
    """Main PBN import task"""
    logger.info(f"Uruchamianie zadania Celery dla sesji importu #{session_id}")
    try:
        session = ImportSession.objects.get(pk=session_id)
        session.status = "running"
        session.task_id = self.request.id
        session.save()

        ImportLog.objects.create(
            session=session, level="info", step="Start", message="Import PBN rozpoczęty"
        )

        # Get configuration
        config = session.config
        # Multi-hosted: konkretna uczelnia z entrypointu, BEZ fallbacku
        # do get_default() (patrz UczelniaManager.get_for_pbn_background).
        uczelnia = Uczelnia.objects.get_for_pbn_background(uczelnia_id)

        # Create PBN client
        try:
            pbn_client = uczelnia.pbn_client(session.user.pbn_token)
        except Exception as e:
            # If PBN client cannot be created, check if we need to configure it
            zaloguj_polkniety_wyjatek(
                "Nie udało się utworzyć klienta PBN dla sesji importu "
                f"#{session_id}; kontynuacja bez klienta",
                logger=logger,
                do_rollbar=True,
            )
            ImportLog.objects.create(
                session=session,
                level="warning",
                step="Setup",
                message=f"Nie można utworzyć klienta PBN: {str(e)}. Próba konfiguracji...",
            )
            # For initial import, we might not have PBN integration enabled yet
            # The ImportManager will handle this
            pbn_client = None

        # Create and run ImportManager
        import_manager = ImportManager(session, pbn_client, config, uczelnia=uczelnia)

        # Run the import
        result = import_manager.run()

        # Update session status based on result
        session.refresh_from_db()
        if session.status == "cancelled":
            # Already cancelled, just update completed_at
            session.completed_at = timezone.now()
            session.save()
        elif result.get("success", False):
            session.status = "completed"
            session.completed_at = timezone.now()
            session.save()
        else:
            # Use mark_failed() to properly set error_traceback
            error_msg = result.get("error", "Import zakończony niepowodzeniem")
            session.mark_failed(error_msg, "")

        ImportLog.objects.create(
            session=session,
            level="success" if session.status == "completed" else "warning",
            step="End",
            message=f"Import zakończony ze statusem: {session.get_status_display()}",
        )

    except ImportSession.DoesNotExist:
        logger.error(f"Sesja {session_id} nie została znaleziona")
    except Exception as e:
        # Report to Rollbar
        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={"session_id": session_id, "task": "run_pbn_import"},
        )

        tb_string = traceback.format_exc()

        try:
            session = ImportSession.objects.get(pk=session_id)
            session.mark_failed(str(e), tb_string)

            ImportLog.objects.create(
                session=session,
                level="critical",
                step="Error",
                message=f"Krytyczny błąd importu: {str(e)}",
                details={"traceback": tb_string},
            )
        except BaseException:
            # Nie udało się nawet ZAPISAĆ błędu (np. baza padła). To NIE może
            # zniknąć po cichu — inaczej krytyczny błąd importu nie zostawia
            # żadnego śladu. Zaloguj z tracebackiem i zgłoś do Rollbar.
            logger.exception(
                "Nie udało się zapisać krytycznego błędu importu dla sesji %s",
                session_id,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "session_id": session_id,
                    "task": "run_pbn_import",
                    "phase": "error_persistence_failed",
                },
            )
        except Exception:
            zaloguj_polkniety_wyjatek(
                "Nie udało się zapisać statusu błędu sesji importu PBN "
                f"#{session_id} po krytycznym błędzie importu",
                logger=logger,
                do_rollbar=True,
            )
