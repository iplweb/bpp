"""Class-based views wizarda importera publikacji.

Każdy widok odpowiada jednemu krokowi (Index → Fetch → Verify → Source →
Authors → Review → Create → Done) plus boczne akcje na autorach i
anulowanie sesji.
"""

import traceback

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from bpp.models import Uczelnia
from bpp.views.api import ostatnia_dyscyplina, ostatnia_jednostka
from crossref_bpp.core import Komparator

from ..forms import AuthorMatchForm, FetchForm, SourceForm, VerifyForm
from ..models import ImportedAuthor, ImportSession
from ..permissions import ImporterPermissionMixin
from ..providers import InputMode, get_provider
from .authors import (
    _auto_match_authors,
    _create_unmatched_authors,
    _orcid_settable_qs,
    _prefill_dyscypliny_z_zgloszen,
)
from .helpers import (
    SESSIONS_PARTIAL,
    STEP_DONE,
    STEP_FETCH,
    _fetch_context,
    _get_crossref_mapper,
    _push_url,
    _render_full_page,
    _sessions_list_context,
    _with_breadcrumbs_oob,
)
from .publikacja import (
    _build_abstracts_list,
    _create_publication,
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
    """Pobierz dane z dostawcy i utwórz sesję."""

    def post(self, request):
        form = FetchForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                STEP_FETCH,
                _fetch_context(form),
            )

        provider_name = form.cleaned_data["provider"]
        request.session["importer_last_provider"] = provider_name
        provider = get_provider(provider_name)

        # Wybierz dane wejściowe wg trybu providera
        if provider.input_mode == InputMode.TEXT:
            raw_input = form.cleaned_data["text_input"]
            error_field = "text_input"
        else:
            raw_input = form.cleaned_data["identifier"]
            error_field = "identifier"

        normalized = provider.validate_identifier(raw_input)
        if normalized is None:
            form.add_error(
                error_field,
                "Nieprawidłowy format danych.",
            )
            return render(
                request,
                STEP_FETCH,
                _fetch_context(form),
            )

        result = provider.fetch(normalized)
        if result is None:
            form.add_error(
                error_field,
                "Nie udało się przetworzyć danych publikacji.",
            )
            return render(
                request,
                STEP_FETCH,
                _fetch_context(form),
            )

        # Dla providerów TEXT, identifier w DB
        # = DOI lub bibtex_key lub skrócony tytuł
        if provider.input_mode == InputMode.TEXT:
            identifier = (
                result.doi or result.extra.get("bibtex_key") or result.title[:100]
            )
        else:
            identifier = normalized

        # Utwórz sesję importu
        session = ImportSession.objects.create(
            created_by=request.user,
            provider_name=provider_name,
            identifier=identifier,
            raw_data=result.raw_data,
            normalized_data={
                "title": result.title,
                "doi": result.doi,
                "year": result.year,
                "authors": result.authors,
                "source_title": result.source_title,
                "source_abbreviation": (result.source_abbreviation),
                "issn": result.issn,
                "e_issn": result.e_issn,
                "isbn": result.isbn,
                "e_isbn": result.e_isbn,
                "publisher": result.publisher,
                "publication_type": (result.publication_type),
                "language": result.language,
                "abstract": result.abstract,
                "volume": result.volume,
                "issue": result.issue,
                "pages": result.pages,
                "url": result.url,
                "license_url": result.license_url,
                "keywords": result.keywords,
                "article_number": result.extra.get("article_number"),
                "original_title": result.extra.get("original_title"),
                "abstracts": _build_abstracts_list(result),
            },
        )

        # Auto-dopasuj typ publikacji via Crossref_Mapper
        mapper = _get_crossref_mapper(result.publication_type)
        if mapper and mapper.charakter_formalny_bpp_id:
            session.charakter_formalny = mapper.charakter_formalny_bpp
            session.jest_wydawnictwem_zwartym = mapper.jest_wydawnictwem_zwartym

        # Auto-dopasuj język
        language_code = result.language
        if not language_code:
            from .helpers import _detect_language

            language_code = _detect_language(result.title, result.abstract)
        if language_code:
            lang_result = Komparator.porownaj_language(language_code)
            if lang_result.rekord_po_stronie_bpp:
                session.jezyk = lang_result.rekord_po_stronie_bpp

        session.save()

        # Auto-dopasuj autorów
        _auto_match_authors(session, result.authors, result.year)
        _prefill_dyscypliny_z_zgloszen(session)

        return _render_verify_step(request, session)


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
    """Utwórz rekord publikacji."""

    def post(self, request, session_id):
        session = get_object_or_404(
            ImportSession,
            pk=session_id,
        )

        try:
            record = _create_publication(session)
        except ValidationError as e:
            error_msg = " ".join(e.messages) if hasattr(e, "messages") else str(e)
            return render(
                request,
                STEP_DONE,
                {
                    "session": session,
                    "error": error_msg,
                    "traceback": None,
                },
            )
        except Exception:
            traceback.print_exc()
            error_msg = "Wystąpił błąd podczas tworzenia rekordu."
            tb_text = None
            if request.user.is_superuser:
                tb_text = traceback.format_exc()
            else:
                error_msg += " Sprawdź logi serwera."
            return render(
                request,
                STEP_DONE,
                {
                    "session": session,
                    "error": error_msg,
                    "traceback": tb_text,
                },
            )

        session.status = ImportSession.Status.COMPLETED
        session.created_record_content_type = ContentType.objects.get_for_model(record)
        session.created_record_id = record.pk
        session.modified_by = request.user
        session.save()

        if "_create_and_pbn" in request.POST:
            from bpp.admin.helpers.pbn_api.gui import (
                sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
            )

            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request, record)

        url = reverse(
            "importer_publikacji:done",
            kwargs={"session_id": session.pk},
        )
        response = render(
            request,
            STEP_DONE,
            {"session": session, "record": record},
        )
        response = _with_breadcrumbs_oob(response, request, session)
        return _push_url(response, url)


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
