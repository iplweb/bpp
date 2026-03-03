import json
import traceback

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from bpp.models import (
    Autor,
    Crossref_Mapper,
    Status_Korekty,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.views.api import (
    ostatnia_dyscyplina,
    ostatnia_jednostka,
)
from crossref_bpp.core import (
    Komparator,
    StatusPorownania,
)
from import_common.normalization import normalize_doi

from .crossref_fields import categorize_crossref_fields
from .dspace_fields import categorize_dspace_fields
from .forms import (
    AuthorMatchForm,
    FetchForm,
    SessionFilterForm,
    SourceForm,
    VerifyForm,
)
from .models import ImportedAuthor, ImportSession
from .permissions import ImporterPermissionMixin
from .providers import (
    InputMode,
    get_provider,
    get_providers_metadata,
)

_POLISH_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def _detect_language(title, abstract=None):
    """Wykryj język na podstawie tytułu i abstraktu.

    Strategia:
    1. Heurystyka polskich znaków diakrytycznych (szybka)
    2. langdetect jako fallback (wolniejsza, dokładniejsza)

    Zwraca kod ISO 639-1 (np. "en", "pl") lub None.
    """
    if not title:
        return None

    # Heurystyka: polskie znaki diakrytyczne
    if _POLISH_DIACRITICS.intersection(title):
        return "pl"

    # Fallback: langdetect
    text = title
    if abstract:
        text = f"{title} {abstract}"

    from langdetect import LangDetectException, detect

    try:
        return detect(text)
    except LangDetectException:
        return None


STEP_FETCH = "importer_publikacji/partials/step_fetch.html"
STEP_VERIFY = "importer_publikacji/partials/step_verify.html"
STEP_SOURCE = "importer_publikacji/partials/step_source.html"
STEP_AUTHORS = "importer_publikacji/partials/step_authors.html"
STEP_REVIEW = "importer_publikacji/partials/step_review.html"
STEP_DONE = "importer_publikacji/partials/step_done.html"
INDEX = "importer_publikacji/index.html"
SESSIONS_PARTIAL = "importer_publikacji/partials/session_list.html"
BREADCRUMBS_OOB = "importer_publikacji/partials/_breadcrumbs_oob.html"

SESSIONS_ALLOWED_SORTS = {
    "created",
    "-created",
    "modified",
    "-modified",
    "created_by__username",
    "-created_by__username",
    "status",
    "-status",
}


def _with_breadcrumbs_oob(response, request, session=None):
    """Dołącz out-of-band breadcrumbs do odpowiedzi HTMX."""
    oob = render_to_string(
        BREADCRUMBS_OOB,
        {"session": session},
        request=request,
    )
    response.content += oob.encode()
    return response


def _render_full_page(request, step_template, context):
    """Renderuj pełną stronę z danym krokiem w wizardzie."""
    context["step_template"] = step_template
    return render(request, INDEX, context)


def _push_url(response, url):
    """Dodaj HX-Push-Url do odpowiedzi HTMX."""
    response["HX-Push-Url"] = url
    return response


def _get_crossref_mapper(publication_type):
    """Znajdź Crossref_Mapper dla danego typu publikacji.

    Zwraca obiekt Crossref_Mapper lub None.
    """
    if not publication_type:
        return None
    enum_key = publication_type.upper().replace("-", "_")
    try:
        val = Crossref_Mapper.CHARAKTER_CROSSREF[enum_key]
    except KeyError:
        return None
    mapper, _created = Crossref_Mapper.objects.get_or_create(
        charakter_crossref=val,
    )
    return mapper


def _fetch_context(form=None, request=None):
    """Kontekst dla kroku fetch (providers_metadata)."""
    if form is None:
        last_provider = None
        if request is not None:
            last_provider = request.session.get("importer_last_provider")
        form = FetchForm(last_provider=last_provider)
    return {
        "form": form,
        "providers_metadata_json": json.dumps(get_providers_metadata()),
    }


def _sessions_queryset(request):
    """Zbuduj queryset sesji z filtrami z GET params."""
    qs = ImportSession.objects.select_related("created_by", "modified_by").exclude(
        status=ImportSession.Status.CANCELLED
    )

    form = SessionFilterForm(request.GET)
    if form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        if date_from:
            qs = qs.filter(created__date__gte=date_from)

        date_to = form.cleaned_data.get("date_to")
        if date_to:
            qs = qs.filter(created__date__lte=date_to)

        title = form.cleaned_data.get("title")
        if title:
            qs = qs.filter(normalized_data__title__icontains=title)

        doi = form.cleaned_data.get("doi")
        if doi:
            qs = qs.filter(normalized_data__doi__icontains=doi)

        provider = form.cleaned_data.get("provider_name")
        if provider:
            qs = qs.filter(provider_name=provider)

        created_by = form.cleaned_data.get("created_by")
        if created_by:
            qs = qs.filter(created_by=created_by)

        modified_by = form.cleaned_data.get("modified_by")
        if modified_by:
            qs = qs.filter(modified_by=modified_by)

    sort = request.GET.get("sort", "-created")
    if sort not in SESSIONS_ALLOWED_SORTS:
        sort = "-created"
    qs = qs.order_by(sort)

    return qs, form, sort


def _sessions_list_context(request):
    """Kontekst listy sesji z filtrami."""
    qs, form, _sort = _sessions_queryset(request)
    return {
        "sessions": qs,
        "filter_form": form,
    }


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


# --- Funkcje renderujące kroki (partiale HTMX) ---


def _find_duplicates(session):
    """Szukaj duplikatów po DOI i tytule w tabelach publikacji.

    Zwraca listę krotek (publikacja, metoda_dopasowania) lub [].
    Szuka bezpośrednio w tabelach Wydawnictwo_Ciagle
    i Wydawnictwo_Zwarte (nie w zmaterializowanym widoku).
    """
    results = []
    seen_pks = set()

    doi = session.normalized_data.get("doi")
    if doi:
        normalized = normalize_doi(doi)
        if normalized:
            for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
                for pub in model.objects.filter(doi__iexact=normalized)[:5]:
                    key = (type(pub).__name__, pub.pk)
                    if key not in seen_pks:
                        seen_pks.add(key)
                        results.append((pub, "DOI"))

    title = session.normalized_data.get("title", "")
    if title and len(title) >= 10:
        for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
            for pub in model.objects.filter(tytul_oryginalny__iexact=title)[:5]:
                key = (type(pub).__name__, pub.pk)
                if key not in seen_pks:
                    seen_pks.add(key)
                    results.append((pub, "tytuł"))

    return results


def _is_crossref_data(raw_data):
    """Heurystyka: czy raw_data to JSON z CrossRef API."""
    if not raw_data or not isinstance(raw_data, dict):
        return False
    return bool({"DOI", "type"} & raw_data.keys())


def _verify_context(request, session, form=None):
    """Przygotuj kontekst dla kroku weryfikacji."""
    pub_type = session.normalized_data.get("publication_type")
    mapper = _get_crossref_mapper(pub_type)

    if form is None:
        initial = {
            "typ_kbn": session.typ_kbn_id,
            "jezyk": session.jezyk_id,
        }
        # Użyj wartości sesji gdy istnieją (user już submitował)
        if session.charakter_formalny_id:
            initial["charakter_formalny"] = session.charakter_formalny_id
            initial["jest_wydawnictwem_zwartym"] = session.jest_wydawnictwem_zwartym
        elif mapper and mapper.charakter_formalny_bpp_id:
            initial["charakter_formalny"] = mapper.charakter_formalny_bpp_id
            initial["jest_wydawnictwem_zwartym"] = mapper.jest_wydawnictwem_zwartym
        form = VerifyForm(initial=initial)

    existing = _find_duplicates(session)

    doi = session.normalized_data.get("doi")
    suggest_crossref = bool(doi and session.provider_name != "CrossRef")

    # Diagnostyka pól z API
    raw_data = session.raw_data
    field_categories = None
    raw_json_pretty = None
    if raw_data and isinstance(raw_data, dict):
        if session.provider_name == "DSpace":
            field_categories = categorize_dspace_fields(raw_data)
        elif _is_crossref_data(raw_data):
            field_categories = categorize_crossref_fields(raw_data)
        raw_json_pretty = json.dumps(
            raw_data,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )

    return {
        "session": session,
        "form": form,
        "existing": existing,
        "auto_charakter": (
            mapper.charakter_formalny_bpp
            if mapper and mapper.charakter_formalny_bpp_id
            else None
        ),
        "auto_zwarte": (mapper.jest_wydawnictwem_zwartym if mapper else None),
        "suggest_crossref": suggest_crossref,
        "crossref_doi": doi if suggest_crossref else None,
        "field_categories": field_categories,
        "raw_json_pretty": raw_json_pretty,
    }


def _render_verify_step(request, session, form=None):
    """Renderuj partial weryfikacji z HX-Push-Url."""
    ctx = _verify_context(request, session, form)
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_VERIFY, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_verify_full(request, session, form=None):
    """Renderuj pełną stronę z krokiem weryfikacji."""
    ctx = _verify_context(request, session, form)
    return _render_full_page(request, STEP_VERIFY, ctx)


def _source_context(request, session, form=None):
    """Przygotuj kontekst dla kroku źródła."""
    if form is None:
        initial = {}

        # Użyj wartości sesji gdy istnieją (user już submitował)
        if session.zrodlo_id:
            initial["zrodlo"] = session.zrodlo_id
        if session.wydawca_id:
            initial["wydawca"] = session.wydawca_id
        wydawca_opis = session.matched_data.get("wydawca_opis", "")
        if wydawca_opis:
            initial["wydawca_opis"] = wydawca_opis

        # Auto-matching tylko gdy brak zapisanych wartości
        if not initial:
            nd = session.normalized_data
            source_title = nd.get("source_title")
            if source_title:
                src = Komparator.porownaj_container_title(source_title)
                if src.rekord_po_stronie_bpp:
                    initial["zrodlo"] = src.rekord_po_stronie_bpp.pk

            publisher = nd.get("publisher")
            if publisher:
                pub = Komparator.porownaj_publisher(publisher)
                if pub.rekord_po_stronie_bpp:
                    initial["wydawca"] = pub.rekord_po_stronie_bpp.pk
                else:
                    initial["wydawca_opis"] = publisher

        form = SourceForm(initial=initial)

    return {"session": session, "form": form}


def _render_source_step(request, session, form=None):
    """Renderuj partial źródła z HX-Push-Url."""
    ctx = _source_context(request, session, form)
    url = reverse(
        "importer_publikacji:source",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_SOURCE, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_source_full(request, session, form=None):
    """Renderuj pełną stronę z krokiem źródła."""
    ctx = _source_context(request, session, form)
    return _render_full_page(request, STEP_SOURCE, ctx)


def _orcid_settable_qs(session):
    """Queryset autorów kwalifikujących się do ustawienia ORCID.

    Warunki:
    - ImportedAuthor ma ORCID od dostawcy (niepusty)
    - Jest dopasowany do Autora w BPP
    - Autor w BPP nie ma ORCID (NULL lub "")
    - Ten sam Autor BPP nie jest dopasowany wielokrotnie w sesji
    """
    all_authors = session.authors.all()

    # Znajdź matched_autor_id pojawiające się więcej niż raz
    dupes = (
        all_authors.filter(matched_autor__isnull=False)
        .values("matched_autor")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .values_list("matched_autor", flat=True)
    )

    return (
        all_authors.filter(
            ~Q(orcid=""),
            matched_autor__isnull=False,
        )
        .filter(
            Q(matched_autor__orcid__isnull=True) | Q(matched_autor__orcid=""),
        )
        .exclude(
            matched_autor__in=dupes,
        )
    )


def _authors_context(request, session):
    """Przygotuj kontekst dla kroku autorów."""
    all_authors = session.authors.select_related(
        "matched_autor",
        "matched_jednostka",
        "matched_dyscyplina",
    ).all()
    total = all_authors.count()

    stats = {
        "total": total,
        "matched": all_authors.exclude(
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
        ).count(),
        "auto_exact": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.AUTO_EXACT)
        ).count(),
        "auto_loose": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.AUTO_LOOSE)
        ).count(),
        "manual": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.MANUAL)
        ).count(),
        "unmatched": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
        ).count(),
    }

    orcid_settable_count = _orcid_settable_qs(session).count()

    return {
        "session": session,
        "authors": all_authors,
        "stats": stats,
        "orcid_settable_count": orcid_settable_count,
    }


def _render_authors_step(request, session, error=None):
    """Renderuj partial autorów z HX-Push-Url."""
    ctx = _authors_context(request, session)
    if error:
        ctx["error"] = error
    url = reverse(
        "importer_publikacji:authors",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_AUTHORS, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_authors_full(request, session):
    """Renderuj pełną stronę z krokiem autorów."""
    ctx = _authors_context(request, session)
    return _render_full_page(request, STEP_AUTHORS, ctx)


def _review_context(request, session):
    """Przygotuj kontekst dla kroku przeglądu."""
    authors = session.authors.select_related(
        "matched_autor",
        "matched_jednostka",
        "matched_dyscyplina",
    ).exclude(matched_autor=None)

    return {
        "session": session,
        "authors": authors,
        "data": session.normalized_data,
    }


def _render_review_step(request, session):
    """Renderuj partial przeglądu z HX-Push-Url."""
    ctx = _review_context(request, session)
    url = reverse(
        "importer_publikacji:review",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_REVIEW, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_review_full(request, session):
    """Renderuj pełną stronę z krokiem przeglądu."""
    ctx = _review_context(request, session)
    return _render_full_page(request, STEP_REVIEW, ctx)


# --- Funkcje pomocnicze ---


def _auto_match_authors(session, authors_data, year):
    """Auto-dopasuj autorów z danych dostawcy."""
    for i, author_data in enumerate(authors_data):
        imported = ImportedAuthor.objects.create(
            session=session,
            order=i,
            family_name=author_data.get("family", ""),
            given_name=author_data.get("given", ""),
            orcid=author_data.get("orcid", ""),
        )

        result = Komparator.porownaj_author(author_data)

        if result.status == StatusPorownania.DOKLADNE:
            bpp_autor = result.rekord_po_stronie_bpp
            if bpp_autor:
                imported.matched_autor = bpp_autor
                imported.match_status = ImportedAuthor.MatchStatus.AUTO_EXACT
                imported.matched_jednostka = bpp_autor.aktualna_jednostka
                if year:
                    dyscyplina = _get_dyscyplina(bpp_autor, year)
                    imported.matched_dyscyplina = dyscyplina
                    if dyscyplina:
                        imported.dyscyplina_source = (
                            ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                        )
        elif result.status == StatusPorownania.LUZNE:
            bpp_autor = result.rekord_po_stronie_bpp
            if bpp_autor:
                imported.matched_autor = bpp_autor
                imported.match_status = ImportedAuthor.MatchStatus.AUTO_LOOSE
                imported.matched_jednostka = bpp_autor.aktualna_jednostka
                if year:
                    dyscyplina = _get_dyscyplina(bpp_autor, year)
                    imported.matched_dyscyplina = dyscyplina
                    if dyscyplina:
                        imported.dyscyplina_source = (
                            ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                        )

        imported.save()


def _get_dyscyplina(autor, year):
    """Pobierz dyscyplinę autora dla danego roku."""
    from bpp.models import Autor_Dyscyplina

    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=year)
        if ad.dyscyplina_naukowa and not ad.subdyscyplina_naukowa:
            return ad.dyscyplina_naukowa
    except Autor_Dyscyplina.DoesNotExist:
        pass
    except Autor_Dyscyplina.MultipleObjectsReturned:
        pass
    return None


def _find_matching_zgloszenie(session):
    """Szukaj pasującego zgłoszenia publikacji po DOI lub tytule.

    Zwraca obiekt Zgloszenie_Publikacji lub None.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    excluded = (
        Zgloszenie_Publikacji.Statusy.ODRZUCONO,
        Zgloszenie_Publikacji.Statusy.SPAM,
    )

    doi = session.normalized_data.get("doi")
    if doi:
        normalized = normalize_doi(doi)
        if normalized:
            zgl = (
                Zgloszenie_Publikacji.objects.filter(
                    doi__iexact=normalized,
                )
                .exclude(status__in=excluded)
                .order_by("-ostatnio_zmieniony")
                .first()
            )
            if zgl:
                return zgl

    title = session.normalized_data.get("title", "")
    if title and len(title) >= 10:
        zgl = (
            Zgloszenie_Publikacji.objects.filter(
                tytul_oryginalny__iexact=title,
            )
            .exclude(status__in=excluded)
            .order_by("-ostatnio_zmieniony")
            .first()
        )
        if zgl:
            return zgl

    return None


def _prefill_dyscypliny_z_zgloszen(session):
    """Uzupełnij brakujące dyscypliny z danych zgłoszeń publikacji.

    Szuka pasującego Zgloszenie_Publikacji (po DOI/tytule)
    i kopiuje dyscypliny dla autorów, którym brakuje.
    Nigdy nie nadpisuje istniejących wartości.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    zgloszenie = _find_matching_zgloszenie(session)
    if not zgloszenie:
        return

    zpa_by_autor = {}
    for zpa in Zgloszenie_Publikacji_Autor.objects.filter(
        rekord=zgloszenie,
    ).select_related("dyscyplina_naukowa", "jednostka"):
        zpa_by_autor[zpa.autor_id] = zpa

    to_update = session.authors.filter(
        matched_autor__isnull=False,
        matched_dyscyplina__isnull=True,
    )

    for imported in to_update:
        zpa = zpa_by_autor.get(imported.matched_autor_id)
        if not zpa:
            continue
        if zpa.dyscyplina_naukowa_id:
            imported.matched_dyscyplina = zpa.dyscyplina_naukowa
            imported.dyscyplina_source = ImportedAuthor.DyscyplinaSource.ZGLOSZENIE
        if not imported.matched_jednostka_id and zpa.jednostka_id:
            imported.matched_jednostka = zpa.jednostka
        imported.save()


@transaction.atomic
def _create_unmatched_authors(session, obca):
    """Utwórz rekordy Autor dla niedopasowanych
    autorów i przypisz do obcej jednostki."""
    unmatched = session.authors.filter(
        match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
    )
    for imported in unmatched:
        orcid = imported.orcid.strip() or None

        # Jeśli ORCID podany i istnieje Autor
        # z takim ORCID -- dopasuj istniejącego
        if orcid:
            existing = Autor.objects.filter(orcid=orcid).first()
            if existing:
                imported.matched_autor = existing
                imported.matched_jednostka = obca
                imported.match_status = ImportedAuthor.MatchStatus.MANUAL
                existing.dodaj_jednostke(obca)
                imported.save()
                continue

        autor = Autor.objects.create(
            imiona=imported.given_name,
            nazwisko=imported.family_name,
            orcid=orcid,
        )
        autor.dodaj_jednostke(obca)

        imported.matched_autor = autor
        imported.matched_jednostka = obca
        imported.match_status = ImportedAuthor.MatchStatus.MANUAL
        imported.save()


def _build_abstracts_list(result):
    """Zbuduj listę streszczeń z FetchedPublication.

    Priorytet:
    1. extra["abstracts"] (z body HTML, WWW provider)
    2. result.abstract (z meta tagów / API)
    """
    abstracts = result.extra.get("abstracts")
    if abstracts:
        return abstracts
    if result.abstract:
        return [{"text": result.abstract, "language": None}]
    return []


def _resolve_jezyk(language_code):
    """Znajdź obiekt Jezyk po kodzie ISO-639 lub CrossRef."""
    if not language_code:
        return None
    from bpp.models import Jezyk

    return Jezyk.objects.filter(skrot_crossref=language_code).first()


def _create_streszczenia(session, record):
    """Utwórz rekordy streszczeń dla publikacji."""
    nd = session.normalized_data
    abstracts = nd.get("abstracts", [])

    # Fallback: pojedynczy abstract z normalized_data
    if not abstracts and nd.get("abstract"):
        abstracts = [{"text": nd["abstract"], "language": None}]

    for abstract in abstracts:
        text = abstract.get("text", "").strip()
        if not text:
            continue

        lang_code = abstract.get("language")
        if not lang_code:
            lang_code = _detect_language(text)

        jezyk = _resolve_jezyk(lang_code)

        record.streszczenia.create(
            streszczenie=text,
            jezyk_streszczenia=jezyk,
        )


@transaction.atomic
def _create_publication(session):
    """Utwórz rekord publikacji na podstawie sesji."""
    normalized_data = session.normalized_data

    common_fields = {
        "tytul_oryginalny": normalized_data.get("title") or "",
        "rok": normalized_data.get("year"),
        "doi": normalized_data.get("doi"),  # DOI accepts null
        "tom": normalized_data.get("volume") or "",
        "strony": normalized_data.get("pages") or "",
        "www": normalized_data.get("url") or "",
        "issn": normalized_data.get("issn") or "",
        "e_issn": normalized_data.get("e_issn") or "",
        "slowa_kluczowe": ", ".join(
            f'"{kw}"' for kw in normalized_data.get("keywords", [])
        ),
        "adnotacje": (f"Dodano przez importer publikacji ({session.provider_name})"),
        "charakter_formalny": session.charakter_formalny,
        "jezyk": session.jezyk,
        "typ_kbn": session.typ_kbn,
        "status_korekty_id": (Status_Korekty.objects.first().pk),
    }

    # original-title z CrossRef → tytul (drugi tytuł)
    original_title = normalized_data.get("original_title")
    if original_title:
        common_fields["tytul"] = original_title

    # article-number z CrossRef → szczegoly
    article_number = normalized_data.get("article_number")
    if article_number:
        common_fields["szczegoly"] = article_number

    if session.jest_wydawnictwem_zwartym:
        record = _create_wydawnictwo_zwarte(session, common_fields, normalized_data)
    else:
        record = _create_wydawnictwo_ciagle(session, common_fields, normalized_data)

    _add_authors_to_record(session, record)
    _create_streszczenia(session, record)

    if session.zrodlo and normalized_data.get("year"):
        from bpp.models.zrodlo import uzupelnij_punktacje_z_zrodla

        uzupelnij_punktacje_z_zrodla(record, session.zrodlo, normalized_data["year"])

    return record


def _create_wydawnictwo_ciagle(session, common_fields, normalized_data):
    """Utwórz Wydawnictwo_Ciagle."""
    common_fields["zrodlo"] = session.zrodlo
    common_fields["nr_zeszytu"] = normalized_data.get("issue") or ""
    return Wydawnictwo_Ciagle.objects.create(**common_fields)


def _create_wydawnictwo_zwarte(session, common_fields, normalized_data):
    """Utwórz Wydawnictwo_Zwarte."""
    common_fields["wydawca"] = session.wydawca
    common_fields["wydawca_opis"] = session.matched_data.get("wydawca_opis", "")
    common_fields["isbn"] = normalized_data.get("isbn") or ""
    common_fields["e_isbn"] = normalized_data.get("e_isbn") or ""

    issue = normalized_data.get("issue")
    if issue:
        existing = common_fields.get("szczegoly", "")
        prefix = f"{existing}, " if existing else ""
        common_fields["szczegoly"] = f"{prefix}nr zeszytu: {issue}"

    publisher_loc = session.raw_data.get("publisher-location", "")
    year = normalized_data.get("year", "")
    if publisher_loc:
        common_fields["miejsce_i_rok"] = f"{publisher_loc} {year}"

    return Wydawnictwo_Zwarte.objects.create(**common_fields)


def _add_authors_to_record(session, record):
    """Dodaj dopasowanych autorów do rekordu."""
    authors = (
        session.authors.exclude(match_status=(ImportedAuthor.MatchStatus.UNMATCHED))
        .select_related(
            "matched_autor",
            "matched_jednostka",
            "matched_dyscyplina",
        )
        .order_by("order")
    )

    typ_aut = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")

    uczelnia = Uczelnia.objects.get_default()
    obca = uczelnia.obca_jednostka if uczelnia else None

    for imported_author in authors:
        if not imported_author.matched_autor or not imported_author.matched_jednostka:
            continue

        zapisany_jako = (
            f"{imported_author.family_name} {imported_author.given_name}"
        ).strip()

        jest_obca = obca and imported_author.matched_jednostka == obca
        afiliuje = not jest_obca

        record.dodaj_autora(
            autor=imported_author.matched_autor,
            jednostka=(imported_author.matched_jednostka),
            zapisany_jako=zapisany_jako,
            typ_odpowiedzialnosci_skrot=typ_aut.skrot,
            dyscyplina_naukowa=(imported_author.matched_dyscyplina),
            afiliuje=afiliuje,
        )
