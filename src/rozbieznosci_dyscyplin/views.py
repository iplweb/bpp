import time

from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.views.generic import RedirectView

from rozbieznosci_dyscyplin.admin import SESSION_KEY_ZADANIA


class NieistniejacaDyscyplina:
    pk = -1
    nazwa = "--"


class RedirectToAdmin(RedirectView):
    def get_redirect_url(self, *args, **kw):
        ctype = ContentType.objects.get(pk=self.kwargs["content_type_id"])
        return (
            f"/admin/{ctype.app_label}/{ctype.model}/"
            f"{int(self.kwargs['object_id'])}/change/"
        )


STAN_ZADANIA = {
    "PENDING": "oczekuje na uruchomienie",
    "RECEIVED": "oczekuje na uruchomienie",
    "STARTED": "w toku",
    "RETRY": "w toku",
    "SUCCESS": "zakończone",
    "FAILURE": "zakończone błędem",
    "REVOKED": "anulowane",
}

# A task still PENDING after this long was lost (worker restart) or its result
# expired (CELERY_RESULT_EXPIRES): Celery reports both as PENDING.
ZADANIE_ZAGUBIONE_PO_SEKUNDACH = 60 * 60

DOMYSLNA_LISTA = (
    "/admin/rozbieznosci_dyscyplin/rozbieznosciview/"
    "?q-l=on&q=rok%3E%3D2022&pracuje_na_uczelni=tak"
)


@login_required
def status_zadania(request, task_id):
    """Progress and result of a background "set discipline" run.

    Only tasks started from this session are shown: the result lists records
    and authors, and Celery task ids are not tied to a user otherwise.
    """
    if not request.user.has_perm("rozbieznosci_dyscyplin.view_rozbieznosciview"):
        raise PermissionDenied

    task_id = str(task_id)
    wpis = next(
        (
            z
            for z in request.session.get(SESSION_KEY_ZADANIA, [])
            if isinstance(z, dict) and z.get("id") == task_id
        ),
        None,
    )
    if wpis is None:
        raise Http404

    powrot = wpis.get("powrot") or ""
    if not powrot.startswith("/admin/rozbieznosci_dyscyplin/"):
        powrot = DOMYSLNA_LISTA

    wynik = AsyncResult(task_id)
    zagubione = (
        wynik.state == "PENDING"
        and time.time() - wpis.get("start", 0) > ZADANIE_ZAGUBIONE_PO_SEKUNDACH
    )

    zmienione, pominiete = [], []
    if wynik.successful():
        for poziom, tresc in wynik.result or []:
            (pominiete if poziom == "warning" else zmienione).append(tresc)

    return render(
        request,
        "rozbieznosci_dyscyplin/status_zadania.html",
        {
            "title": "Ustawianie dyscyplin w tle",
            "stan": STAN_ZADANIA.get(wynik.state, wynik.state),
            "w_toku": not wynik.ready() and not zagubione,
            "zagubione": zagubione,
            "sukces": wynik.successful(),
            "blad": wynik.failed(),
            "zmienione": zmienione,
            "pominiete": pominiete,
            "powrot": powrot,
        },
    )
