from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
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


@login_required
def status_zadania(request, task_id):
    """Progress and result of a background "set discipline" run.

    Only tasks started from this session are shown: the result lists records
    and authors, and Celery task ids are not tied to a user otherwise.
    """
    task_id = str(task_id)
    if task_id not in request.session.get(SESSION_KEY_ZADANIA, []):
        raise Http404

    wynik = AsyncResult(task_id)
    gotowe = wynik.ready()
    komunikaty = wynik.result if wynik.successful() else []
    return render(
        request,
        "rozbieznosci_dyscyplin/status_zadania.html",
        {
            "title": "Ustawianie dyscyplin w tle",
            "stan": STAN_ZADANIA.get(wynik.state, wynik.state),
            "gotowe": gotowe,
            "blad": wynik.failed(),
            "komunikaty": komunikaty or [],
        },
    )
