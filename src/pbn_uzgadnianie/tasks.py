"""Zadanie w tle operacji „Uzgodnij z PBN” (FD#477)."""

import logging
import sys

from bpp.zglaszanie_bledow import capture_exception
from django_bpp.celery_tasks import app

logger = logging.getLogger(__name__)


def wykonaj_uzgodnienie(uzgodnienie, nadzorca=None):
    """Buduje klienta PBN i uruchamia silnik; błąd przebiegu zapisuje w nim.

    Wspólne dla zadania w tle i komendy ``pbn_uzgodnij``.
    """
    from pbn_downloader_app.tasks import validate_pbn_user

    from .models import UzgodnienieZPBN
    from .silnik import uzgodnij, zapisz_przerwany

    uzgodnienie.wpisy_czesciowe = []
    try:
        _user, pbn_user = validate_pbn_user(uzgodnienie.user_id)
        client = uzgodnienie.uczelnia.pbn_client(pbn_user.pbn_token)
        return uzgodnij(uzgodnienie, client, nadzorca)
    except Exception as e:
        # Granica zadania: przebieg MUSI skończyć jako „błąd” (inaczej wisi
        # jako aktywny i blokuje kolejne), a wyjątek idzie dalej — z pełnym
        # tracebackiem do logu i monitoringu.
        logger.exception("Uzgodnienie z PBN #%s przerwane błędem", uzgodnienie.pk)
        capture_exception(sys.exc_info(), extra={"uzgodnienie": uzgodnienie.pk})
        zapisz_przerwany(
            uzgodnienie,
            UzgodnienieZPBN.Status.BLAD,
            "Przerwano z powodu błędu",
            blad=f"{type(e).__name__}: {e}",
        )
        raise


@app.task
def uzgodnij_z_pbn(uzgodnienie_id):
    from .models import UzgodnienieZPBN
    from .silnik import NadzorcaBazy

    uzgodnienie = UzgodnienieZPBN.objects.select_related("uczelnia", "user").get(
        pk=uzgodnienie_id
    )
    if uzgodnienie.status != UzgodnienieZPBN.Status.OCZEKUJE:
        # Zadanie doręczone drugi raz (np. po restarcie workera) — przebieg
        # już ruszył albo się skończył; nie zaczynamy go od nowa.
        logger.warning(
            "Uzgodnienie z PBN #%s ma status %s — pomijam ponowne uruchomienie",
            uzgodnienie.pk,
            uzgodnienie.status,
        )
        return

    nadzorca = NadzorcaBazy(uzgodnienie.pk)
    try:
        wykonaj_uzgodnienie(uzgodnienie, nadzorca)
    finally:
        nadzorca.zamknij()
