from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_common.okres import ustaw_okres


@login_required
@require_POST
def wybierz_okres(request):
    """Zapamiętaj w sesji okres ewaluacji wybrany w górnej belce i wróć na
    stronę, z której przyszło żądanie."""
    try:
        pk = int(request.POST.get("okres", ""))
    except ValueError as e:
        raise Http404("Nieprawidłowy okres ewaluacji") from e
    okres = get_object_or_404(OkresEwaluacji, pk=pk)
    ustaw_okres(request, okres)
    dalej = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(
        dalej, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        dalej = "/"
    return redirect(dalej)
