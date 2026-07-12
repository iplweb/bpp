"""Celery taski aplikacji zgłoszeń publikacji."""

from celery import shared_task
from celery.utils.log import get_task_logger

from zglos_publikacje.cleanup import wyczysc_tmp_pliki

logger = get_task_logger(__name__)


@shared_task
def wyczysc_zglos_tmp_pliki(older_than_hours: int = 24) -> dict:
    """Cykliczna retencja porzuconych plików tmp kreatora zgłoszeń.

    Rejestrowany w `CELERYBEAT_SCHEDULE`. Rdzeń wspólny z management-commandą
    `wyczysc_zglos_tmp`. Worker montuje wolumen media (jak przy
    `remove_old_integrator_files` / `remove_old_oswiadczenia_export_files`),
    więc kasowanie plików pod `MEDIA_ROOT` działa.
    """
    wynik = wyczysc_tmp_pliki(older_than_hours=older_than_hours)
    if wynik["katalog_nieobecny"]:
        logger.info("wyczysc_zglos_tmp_pliki: katalog tmp nie istnieje — pomijam.")
    else:
        logger.info(
            "wyczysc_zglos_tmp_pliki: skasowano %s plików (%s bajtów), pominięto %s.",
            wynik["skasowane"],
            wynik["skasowane_bajty"],
            wynik["pominiete"],
        )
    return wynik
