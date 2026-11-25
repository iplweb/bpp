from django_bpp.celery_tasks import app
from long_running.util import wait_for_object


@app.task
def pobierz_odpowiedniki_z_pbn(pk):
    """Grupowe pobieranie odpowiedników z PBN (FD#516, FD#519) — odczyt."""
    from pbn_integrator.models import PobieranieOdpowiednikowPBN
    from pbn_integrator.pobieranie_odpowiednikow import przejmij, wykonaj

    wait_for_object(PobieranieOdpowiednikowPBN, pk)
    zlecenie = przejmij(pk)
    if zlecenie is None:
        # Zadanie doręczone drugi raz — zlecenie już ktoś wykonuje/wykonał.
        return
    wykonaj(zlecenie)
