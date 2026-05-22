"""Class-based views wizarda importera publikacji.

Każdy widok odpowiada jednemu krokowi (Index → Fetch → Verify → Source →
Authors → Review → Create → Done) plus boczne akcje na autorach i
anulowanie sesji.
"""

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from bpp.models import Uczelnia
from bpp.views.api import ostatnia_dyscyplina, ostatnia_jednostka

from ..forms import AuthorMatchForm, FetchForm, SourceForm, VerifyForm
from ..models import ImportedAuthor, ImportSession
from ..permissions import ImporterPermissionMixin
from ..providers import InputMode, get_provider
from ..tasks import create_publication_task, fetch_session_task
from .authors import (
    _create_unmatched_authors,
    _orcid_settable_qs,
)
from .helpers import (
    SESSIONS_PARTIAL,
    STEP_DONE,
    STEP_FETCH,
    _fetch_context,
    _push_url,
    _render_full_page,
    _sessions_list_context,
    _with_breadcrumbs_oob,
)
from .steps import (
    _is_chapter,
    _render_authors_step,
    _render_review_step,
    _render_source_step,
    _render_verify_full,
    _render_verify_step,
)


class SessionListView(ImporterPermissionMixin, View):
    """Lista sesji z filtrami, sortowaniem i paginacją."""

    def get(self, request):
        ctx = _sessions_list_context(request)
        if request.headers.get("HX-Request"):
            return render(request, SESSIONS_PARTIAL, ctx)
        # Fallback: pełna strona z formularzem fetch
        fetch_ctx = _fetch_context(request=request)
        fetch_ctx.update(ctx)
        return _render_full_page(request, STEP_FETCH, fetch_ctx)


class IndexView(ImporterPermissionMixin, View):
    """Strona główna importera."""

    def get(self, request):
        initial = {}
        if request.GET.get("provider"):
            initial["provider"] = request.GET["provider"]
        if request.GET.get("identifier"):
            initial["identifier"] = request.GET["identifier"]

        if initial:
            form = FetchForm(initial=initial)
        else:
            form = None

        ctx = _fetch_context(form, request=request)
        if request.headers.get("HX-Request"):
            ctx.update(_sessions_list_context(request))
            response = render(request, STEP_FETCH, ctx)
            return _with_breadcrumbs_oob(response, request)
        sessions_ctx = _sessions_list_context(request)
        ctx.update(sessions_ctx)
        return _render_full_page(request, STEP_FETCH, ctx)


class FetchView(ImporterPermissionMixin, View):
    """Walidacja identyfikatora + utworzenie sesji + enqueue Celery task-a."""

    def post(self, request):
        form = FetchForm(request.POST)
        if not form.is_valid():
            return render(request, STEP_FETCH, _fetch_context(form))

        provider_name = form.cleaned_data["provider"]
        request.session["importer_last_provider"] = provider_name
        provider = get_provider(provider_name)

        if provider.input_mode == InputMode.TEXT:
            raw_input = form.cleaned_data["text_input"]
            error_field = "text_input"
        else:
            raw_input = form.cleaned_data["identifier"]
            error_field = "identifier"

        normalized = provider.validate_identifier(raw_input)
        if normalized is None:
            help_hint = getattr(provider, "input_help_text", "")
            placeholder = getattr(provider, "input_placeholder", "")
            msg = f"Nie rozpoznano formatu dla dostawcy „{provider.name}”."
            if help_hint:
                msg += f" Oczekiwany format: {help_hint}"
            if placeholder:
                msg += f" Przykład: {placeholder}"
            form.add_error(error_field, msg)
            return render(request, STEP_FETCH, _fetch_context(form))

        # Idempotency (C2): jesli juz jest sesja in-flight tego samego usera
        # dla tego samego (provider, identifier), nie startuj kolejnej —
        # zredirectuj do istniejacej. Defense przed double-click i refresh.
        recent_in_flight = (
            ImportSession.objects.filter(
                created_by=request.user,
                provider_name=provider_name,
                identifier=normalized,
                status__in=[
                    ImportSession.Status.FETCHING,
                    ImportSession.Status.FETCHED,
                ],
            )
            .order_by("-created")
            .first()
        )
        if recent_in_flight is not None:
            url = recent_in_flight.get_continue_url()
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = url
                return response
            return HttpResponseRedirect(url)

        session = ImportSession.objects.create(
            created_by=request.user,
            provider_name=provider_name,
            identifier=normalized,
            status=ImportSession.Status.FETCHING,
            raw_data={},
            normalized_data={},
        )

        task = fetch_session_task.delay(session.pk, request.user.pk)
        session.celery_task_id = task.id
        session.save(update_fields=["celery_task_id"])

        url = reverse(
            "importer_publikacji:task-status",
            kwargs={"session_id": session.pk},
        )
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)


class VerifyView(ImporterPermissionMixin, View):
    """Weryfikacja typu publikacji i duplikatów."""

    def get(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        if request.headers.get("HX-Request"):
            return _render_verify_step(request, session)
        return _render_verify_full(request, session)

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        form = VerifyForm(request.POST)

        if not form.is_valid():
            return _render_verify_step(request, session, form=form)

        session.charakter_formalny = form.cleaned_data["charakter_formalny"]
        session.typ_kbn = form.cleaned_data["typ_kbn"]
        session.jezyk = form.cleaned_data["jezyk"]
        session.jest_wydawnictwem_zwartym = form.cleaned_data[
            "jest_wydawnictwem_zwartym"
        ]
        session.status = ImportSession.Status.VERIFIED
        session.modified_by = request.user
        session.save()

        return _render_source_step(request, session)


class SourceView(ImporterPermissionMixin, View):
    """Dopasowanie źródła (czasopisma/wydawcy)."""

    def get(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        if request.headers.get("HX-Request"):
            return _render_source_step(request, session)
        from .steps import _render_source_full

        return _render_source_full(request, session)

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        form = SourceForm(request.POST)

        if not form.is_valid():
            return _render_source_step(request, session, form=form)

        if session.jest_wydawnictwem_zwartym:
            wydawca = form.cleaned_data.get("wydawca")
            wydawca_opis = form.cleaned_data.get("wydawca_opis", "")
            if not wydawca and not wydawca_opis.strip():
                form.add_error(
                    "wydawca",
                    "Podaj wydawcę lub wpisz szczegóły wydawcy.",
                )
                return _render_source_step(request, session, form=form)

            # Rozdział wymaga wydawnictwa nadrzędnego
            if _is_chapter(session):
                wn = form.cleaned_data.get("wydawnictwo_nadrzedne")
                wn_pbn = form.cleaned_data.get("wydawnictwo_nadrzedne_w_pbn")
                if not wn and not wn_pbn:
                    form.add_error(
                        "wydawnictwo_nadrzedne",
                        "Dla rozdziału wymagane jest wydawnictwo nadrzędne.",
                    )
                    return _render_source_step(request, session, form=form)
                if wn and wn_pbn:
                    form.add_error(
                        "wydawnictwo_nadrzedne",
                        "Podaj tylko jedno: wydawnictwo"
                        " nadrzędne lub wydawnictwo"
                        " nadrzędne w PBN.",
                    )
                    return _render_source_step(request, session, form=form)
        else:
            if not form.cleaned_data.get("zrodlo"):
                form.add_error(
                    "zrodlo",
                    "Źródło jest wymagane dla wydawnictwa ciągłego.",
                )
                return _render_source_step(request, session, form=form)

        session.zrodlo = form.cleaned_data["zrodlo"]
        session.wydawca = form.cleaned_data["wydawca"]
        session.matched_data["wydawca_opis"] = form.cleaned_data.get("wydawca_opis", "")
        session.wydawnictwo_nadrzedne = form.cleaned_data.get("wydawnictwo_nadrzedne")
        session.wydawnictwo_nadrzedne_w_pbn = form.cleaned_data.get(
            "wydawnictwo_nadrzedne_w_pbn"
        )
        session.status = ImportSession.Status.SOURCE_MATCHED
        session.modified_by = request.user
        session.save()

        return _render_authors_step(request, session)


class AuthorsView(ImporterPermissionMixin, View):
    """Lista autorów z paginacją."""

    def get(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        if request.headers.get("HX-Request"):
            return _render_authors_step(request, session)
        from .steps import _render_authors_full

        return _render_authors_full(request, session)


class AuthorMatchView(ImporterPermissionMixin, View):
    """Aktualizacja dopasowania pojedynczego autora."""

    def post(self, request, session_id, author_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        imported_author = get_object_or_404(
            ImportedAuthor,
            pk=author_id,
            session=session,
        )

        form = AuthorMatchForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "importer_publikacji/partials/author_row.html",
                {
                    "session": session,
                    "author": imported_author,
                },
            )

        if form.cleaned_data.get("autor"):
            imported_author.matched_autor = form.cleaned_data["autor"]
            imported_author.match_status = ImportedAuthor.MatchStatus.MANUAL
            imported_author.matched_jednostka = form.cleaned_data.get("jednostka")
            imported_author.matched_dyscyplina = form.cleaned_data.get("dyscyplina")

            if imported_author.matched_dyscyplina:
                imported_author.dyscyplina_source = (
                    ImportedAuthor.DyscyplinaSource.MANUAL
                )

            if imported_author.matched_autor and not imported_author.matched_jednostka:
                imported_author.matched_jednostka = ostatnia_jednostka(
                    request,
                    imported_author.matched_autor,
                )
            if imported_author.matched_autor and not imported_author.matched_dyscyplina:
                year = session.normalized_data.get("year")
                if year:
                    dyscyplina = ostatnia_dyscyplina(
                        request,
                        imported_author.matched_autor,
                        year,
                    )
                    imported_author.matched_dyscyplina = dyscyplina
                    if dyscyplina:
                        imported_author.dyscyplina_source = (
                            ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                        )
        else:
            imported_author.match_status = ImportedAuthor.MatchStatus.UNMATCHED
            imported_author.matched_autor = None
            imported_author.matched_jednostka = None
            imported_author.matched_dyscyplina = None
            imported_author.dyscyplina_source = ""

        imported_author.save()

        return render(
            request,
            "importer_publikacji/partials/author_row.html",
            {
                "session": session,
                "author": imported_author,
            },
        )


class AuthorsConfirmView(ImporterPermissionMixin, View):
    """Potwierdź wszystkie dopasowania autorów."""

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )

        unmatched = session.authors.filter(
            matched_autor=None,
        ).count()
        if unmatched:
            return _render_authors_step(
                request,
                session,
                error=(
                    f"Nie można przejść dalej — "
                    f"pozostało {unmatched} "
                    f"niedopasowanych autorów. "
                    f"Dopasuj ich ręcznie lub utwórz "
                    f"jako nowych autorów w systemie."
                ),
            )

        session.status = ImportSession.Status.AUTHORS_MATCHED
        session.modified_by = request.user
        session.save()

        return _render_review_step(request, session)


class CreateUnmatchedAuthorsView(ImporterPermissionMixin, View):
    """Utwórz rekordy Autor dla niedopasowanych."""

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        uczelnia = Uczelnia.objects.get_for_request(request)
        obca = uczelnia.obca_jednostka if uczelnia else None

        if not obca:
            return _render_authors_step(
                request,
                session,
                error=(
                    "Brak skonfigurowanej obcej"
                    " jednostki w ustawieniach"
                    " uczelni. Skontaktuj się"
                    " z administratorem."
                ),
            )

        _create_unmatched_authors(session, obca)
        return _render_authors_step(request, session)


class AuthorSetOrcidView(ImporterPermissionMixin, View):
    """Ustaw ORCID pojedynczemu autorowi w BPP."""

    def post(self, request, session_id, author_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        imported = get_object_or_404(
            ImportedAuthor.objects.select_related("matched_autor"),
            pk=author_id,
            session=session,
        )

        if (
            not imported.orcid
            or not imported.matched_autor
            or imported.matched_autor.orcid
        ):
            return HttpResponseBadRequest("Warunki ustawienia ORCID nie są spełnione.")

        imported.matched_autor.orcid = imported.orcid
        imported.matched_autor.save(update_fields=["orcid"])

        return render(
            request,
            "importer_publikacji/partials/author_row.html",
            {"session": session, "author": imported},
        )


class AuthorsSetOrcidsView(ImporterPermissionMixin, View):
    """Ustaw ORCIDy grupowo autorom w BPP."""

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        settable = _orcid_settable_qs(session)
        for imported in settable.select_related("matched_autor"):
            imported.matched_autor.orcid = imported.orcid
            imported.matched_autor.save(update_fields=["orcid"])

        return _render_authors_step(request, session)


class ReviewView(ImporterPermissionMixin, View):
    """Przegląd końcowy przed utworzeniem rekordu."""

    def get(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        if request.headers.get("HX-Request"):
            return _render_review_step(request, session)
        from .steps import _render_review_full

        return _render_review_full(request, session)


class CreateView(ImporterPermissionMixin, View):
    """Enqueueuje create_publication_task; redirect na task-status."""

    def post(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)

        # Idempotency (C2): jesli sesja juz jest w trakcie tworzenia lub
        # zakonczona — nie enqueueuj kolejnego taska. Redirect do
        # task-status (lub done dla COMPLETED) zamiast podwojnego POST-a.
        if session.status in (
            ImportSession.Status.CREATING,
            ImportSession.Status.COMPLETED,
        ):
            url = session.get_continue_url()
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = url
                return response
            return HttpResponseRedirect(url)

        also_pbn = "_create_and_pbn" in request.POST

        # Persist for retry path (Task 10 reads this)
        session.matched_data["pbn_export_pending"] = also_pbn
        session.status = ImportSession.Status.CREATING
        session.save(update_fields=["matched_data", "status"])

        task = create_publication_task.delay(session.pk, request.user.pk, also_pbn)
        session.celery_task_id = task.id
        session.save(update_fields=["celery_task_id"])

        url = reverse(
            "importer_publikacji:task-status",
            kwargs={"session_id": session.pk},
        )
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)


class DoneView(ImporterPermissionMixin, View):
    """Strona potwierdzenia utworzenia rekordu (GET)."""

    def get(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        record = session.created_record
        return _render_full_page(
            request,
            STEP_DONE,
            {"session": session, "record": record},
        )


class CancelView(ImporterPermissionMixin, View):
    """Anuluj sesję importu."""

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )
        session.status = ImportSession.Status.CANCELLED
        session.modified_by = request.user
        session.save()
        url = reverse("importer_publikacji:index")
        ctx = _fetch_context(request=request)
        ctx["cancelled"] = True
        ctx.update(_sessions_list_context(request))
        response = render(request, STEP_FETCH, ctx)
        response = _with_breadcrumbs_oob(response, request)
        return _push_url(response, url)
