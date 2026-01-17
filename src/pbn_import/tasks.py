"""Celery tasks for PBN import"""

import sys
import traceback

import rollbar
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from bpp.models import Uczelnia

from .models import ImportLog, ImportSession
from .utils import ImportManager


def send_websocket_update(session, data):
    """Send update via WebSocket"""
    channel_layer = get_channel_layer()
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"import_{session.id}", {"type": "import_update", "data": data}
            )
        except Exception as e:
            print(f"WebSocket error: {e}")


def update_progress(session, step_name, progress, message=None):
    """Update session progress"""
    session.current_step = step_name
    session.current_step_progress = progress

    # The overall_progress is calculated as a property, no need to set it
    session.save()

    # Log the progress
    if message:
        ImportLog.objects.create(
            session=session, level="info", step=step_name, message=message
        )

    # Send WebSocket update (overall_progress is calculated from the property)
    send_websocket_update(
        session,
        {
            "type": "progress_update",
            "step": step_name,
            "progress": progress,
            "overall_progress": session.overall_progress,  # This reads the property
            "message": message,
        },
    )


@shared_task(bind=True)
def run_pbn_import(self, session_id):
    """Main PBN import task"""
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
        uczelnia = Uczelnia.objects.get_default()

        if not uczelnia:
            raise Exception("Brak konfiguracji uczelni")

        # Create PBN client
        try:
            pbn_client = uczelnia.pbn_client(session.user.pbn_token)
        except Exception as e:
            # If PBN client cannot be created, check if we need to configure it
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
        import_manager = ImportManager(session, pbn_client, config)

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

        # Send completion notification
        send_websocket_update(
            session,
            {
                "type": "completion",
                "success": session.status == "completed",
                "message": f"Import #{session.id} został zakończony",
            },
        )

    except ImportSession.DoesNotExist:
        print(f"Sesja {session_id} nie została znaleziona")
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

            send_websocket_update(
                session,
                {
                    "type": "completion",
                    "success": False,
                    "message": f"Import #{session.id} zakończył się błędem",
                },
            )
        except BaseException:
            pass
