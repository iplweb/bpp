"""Widoki importu wielu DOI naraz (FD#483).

Logika (parsowanie listy, sprawdzenie w BPP/PBN, wiersze ekranu zbiorczego)
jest w :mod:`importer_publikacji.wiele_doi`; pobieranie w tle — w
``tasks.pobierz_paczke_doi_task``.
"""

from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from bpp.models import Uczelnia

from ..forms import WieleDoiForm
from ..models import MultipleWorksImport, MultipleWorksImportEntry
from ..permissions import ImporterPermissionMixin
from ..tasks import pobierz_paczke_doi_task
from ..wiele_doi import (
    DOSTAWCA_DOI,
    kontekst_paczki_doi,
    limit_doi,
    pobieranie_przerwane,
)
from .helpers import (
    BATCH_DETAIL_DOI,
    STEP_WIELE_DOI,
    _is_htmx_partial,
    _render_full_page,
    _with_breadcrumbs_oob,
)

# Ile ostatnich paczek pokazujemy pod formularzem.
_OSTATNIE_PACZKI = 10


def _url_paczki(batch_id):
    return reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch_id})


def _utworz_paczke_doi(request, surowy_tekst, lista):
    """Utwórz paczkę DOI z wpisami: najpierw rozpoznane numery DOI, potem
    linie nierozpoznane (jako wpisy z błędem — widoczne, ale niepobierane)."""
    batch = MultipleWorksImport.objects.create(
        created_by=request.user,
        uczelnia=Uczelnia.objects.get_for_request(request),
        provider_name=DOSTAWCA_DOI,
        raw_input=surowy_tekst,
    )
    wpisy = [
        MultipleWorksImportEntry(parent=batch, order=i, raw_bibtex=doi)
        for i, doi in enumerate(lista.doi)
    ]
    wpisy += [
        MultipleWorksImportEntry(
            parent=batch,
            order=len(lista.doi) + i,
            raw_bibtex=linia,
            parse_error="Nie rozpoznano numeru DOI w tej linii.",
        )
        for i, linia in enumerate(lista.nierozpoznane)
    ]
    MultipleWorksImportEntry.objects.bulk_create(wpisy)
    return batch


class WieleDoiView(ImporterPermissionMixin, View):
    """Ekran „Import wielu DOI”: pole na listę numerów DOI.

    POST tworzy paczkę i zleca pobieranie w tle; rekordów publikacji nie
    tworzy — każdą pracę redaktor przechodzi potem w kreatorze.
    """

    def _kontekst(self, form):
        paczki = (
            self.scope_do_uczelni(
                MultipleWorksImport.objects.filter(provider_name=DOSTAWCA_DOI)
            )
            .select_related("created_by")
            .annotate(liczba_wpisow=Count("entries"))
            .order_by("-created")[:_OSTATNIE_PACZKI]
        )
        return {"form": form, "limit": limit_doi(), "ostatnie_paczki": paczki}

    def _render(self, request, form):
        ctx = self._kontekst(form)
        if _is_htmx_partial(request):
            response = render(request, STEP_WIELE_DOI, ctx)
            return _with_breadcrumbs_oob(response, request)
        return _render_full_page(request, STEP_WIELE_DOI, ctx)

    def get(self, request):
        return self._render(request, WieleDoiForm())

    def post(self, request):
        form = WieleDoiForm(request.POST)
        if not form.is_valid():
            return _render_full_page(request, STEP_WIELE_DOI, self._kontekst(form))

        batch = _utworz_paczke_doi(request, form.cleaned_data["lista_doi"], form.lista)
        pobierz_paczke_doi_task.delay(batch.pk, request.user.pk)
        return HttpResponseRedirect(_url_paczki(batch.pk))


class BatchResumeView(ImporterPermissionMixin, View):
    """Wznów pobieranie paczki DOI, gdy zadanie w tle zostało przerwane.

    Działa tylko, gdy pobieranie faktycznie stoi (patrz
    ``wiele_doi.pobieranie_przerwane``) — inaczej powtórzony POST uruchomiłby
    drugie zadanie obok pracującego.
    """

    def post(self, request, batch_id):
        batch = self.get_scoped_or_404(
            MultipleWorksImport, pk=batch_id, provider_name=DOSTAWCA_DOI
        )
        entries = list(batch.entries.all())
        if pobieranie_przerwane(batch, entries):
            # Odśwież znak życia PRZED zleceniem — drugi klik nie zleci
            # kolejnego zadania.
            MultipleWorksImport.objects.filter(pk=batch.pk).update(
                modified=timezone.now()
            )
            pobierz_paczke_doi_task.delay(batch.pk, request.user.pk)
        return HttpResponseRedirect(_url_paczki(batch.pk))


def render_paczka_doi(request, batch, entries):
    """Ekran zbiorczy paczki DOI — pełna strona albo sam fragment (gdy
    strona odświeża się sama w trakcie pobierania)."""
    ctx = kontekst_paczki_doi(batch, entries)
    ctx["url_paczki"] = _url_paczki(batch.pk)
    if _is_htmx_partial(request):
        return render(request, BATCH_DETAIL_DOI, ctx)
    return _render_full_page(request, BATCH_DETAIL_DOI, ctx)
