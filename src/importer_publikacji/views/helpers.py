"""Pomocnicze funkcje i stałe wspólne dla wszystkich kroków wizarda.

Zawiera:
- ścieżki szablonów partiali HTMX,
- wykrywanie języka tytułu (heurystyka + langdetect),
- mapowanie typu publikacji CrossRef → BPP,
- kontekst dla kroku fetch / listy sesji,
- pomocnicze nakładki HTMX (HX-Push-Url, OOB breadcrumbs).
"""

import json

from django.shortcuts import render
from django.template.loader import render_to_string

from bpp.models import Crossref_Mapper

from ..forms import FetchForm, SessionFilterForm
from ..models import ImportSession
from ..providers import get_providers_metadata

_POLISH_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


STEP_FETCH = "importer_publikacji/partials/step_fetch.html"
STEP_VERIFY = "importer_publikacji/partials/step_verify.html"
STEP_SOURCE = "importer_publikacji/partials/step_source.html"
STEP_AUTHORS = "importer_publikacji/partials/step_authors.html"
STEP_PUNKTACJA = "importer_publikacji/partials/step_punktacja.html"
STEP_PBN = "importer_publikacji/partials/step_pbn.html"
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


def _is_htmx_partial(request):
    """Czy zwrócić partial (fragment) czy pełną stronę dla GET-a kroku.

    ``True`` tylko dla ŻYWEGO żądania HTMX (swap fragmentu do
    ``#importer-wizard``). ``False`` dla zwykłego GET-a ORAZ dla
    przywracania historii przez przeglądarkę (Back/Forward).

    HTMX przy przywracaniu historii (cache-miss) wysyła ZARÓWNO
    ``HX-Request`` jak i ``HX-History-Restore-Request`` — wtedy oczekuje
    PEŁNEJ strony do podmiany ``<body>``. Zwrócenie partiala rozwalało
    wtedy layout wizarda i podwajało widżety select2 („drugi select").
    Dlatego history-restore traktujemy jak zwykłe wejście GET-em (pełna
    strona). Dodatkowo ``index.html`` ma ``hx-history="false"``, żeby
    HTMX nie przywracał nieświeżych snapshotów, tylko zawsze pytał serwer.
    """
    if request.headers.get("HX-History-Restore-Request"):
        return False
    return bool(request.headers.get("HX-Request"))


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
        defaults={
            "jest_wydawnictwem_zwartym": (
                Crossref_Mapper.default_jest_wydawnictwem_zwartym(val)
            ),
        },
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
