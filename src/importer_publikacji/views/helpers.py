"""Pomocnicze funkcje i stałe wspólne dla wszystkich kroków wizarda.

Zawiera:
- ścieżki szablonów partiali HTMX,
- wykrywanie języka tytułu (heurystyka + langdetect),
- mapowanie typu publikacji CrossRef → BPP,
- kontekst dla kroku fetch / listy sesji,
- pomocnicze nakładki HTMX (HX-Push-Url, OOB breadcrumbs).
"""

from django.shortcuts import render
from django.template.loader import render_to_string

from bpp.models import Crossref_Mapper

from ..forms import FetchForm, SessionFilterForm
from ..models import ImportSession, MultipleWorksImport
from ..permissions import scope_import_do_uczelni
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
STEP_LANDING = "importer_publikacji/partials/step_landing.html"
INDEX = "importer_publikacji/index.html"
SESSIONS_PARTIAL = "importer_publikacji/partials/session_list.html"
BATCH_DETAIL = "importer_publikacji/partials/batch_detail.html"
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


def _fetch_context(form=None, request=None, provider_name=None):
    """Kontekst kroku fetch dla POJEDYNCZEGO wybranego providera.

    W kaflowym/deep-linkowym flow provider jest zawsze znany (``?provider=``
    z kafla albo POST). Zwracamy metadane TEGO JEDNEGO providera
    (``provider_meta``) zamiast całej mapy — szablon renderuje wyłącznie
    właściwe pole (identyfikator albo textarea), bez radiowego wyboru źródła
    i bez listy sesji pod spodem.
    """
    metadata = get_providers_metadata()
    if provider_name is None and form is not None:
        provider_name = form.data.get("provider") or form.initial.get("provider")
    if form is None:
        last_provider = None
        if request is not None:
            last_provider = request.session.get("importer_last_provider")
        form = FetchForm(last_provider=last_provider)
        if provider_name is None:
            provider_name = form.initial.get("provider")
    return {
        "form": form,
        "provider_name": provider_name,
        "provider_meta": metadata.get(provider_name),
    }


def _sessions_queryset(request):
    """Zbuduj queryset sesji z filtrami z GET params."""
    qs = ImportSession.objects.select_related("created_by", "modified_by").exclude(
        status=ImportSession.Status.CANCELLED
    )
    # Izolacja multi-host: redaktor widzi tylko sesje swojej uczelni (uwaga #3).
    qs = scope_import_do_uczelni(qs, request)

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


# Statusy sesji uznawane za "zakończone" (nie liczą się do licznika importów
# w toku na kaflowej stronie głównej): sukces, anulowanie przez operatora
# i trwały błąd (który i tak wymaga ręcznego retry, nie "wisi" biernie).
_SESSION_DONE_STATUSES = (
    ImportSession.Status.COMPLETED,
    ImportSession.Status.CANCELLED,
    ImportSession.Status.IMPORT_FAILED,
)


def _in_progress_sessions_count(request) -> int:
    """Liczba pojedynczych sesji importu, które nie są zakończone (w uczelni
    oglądającego — multi-host)."""
    qs = ImportSession.objects.exclude(status__in=_SESSION_DONE_STATUSES)
    return scope_import_do_uczelni(qs, request).count()


def _in_progress_batches_count(request) -> int:
    """Liczba paczek (``MultipleWorksImport``), które nie są w całości
    przetworzone (nie wszystkie wpisy zaimportowane lub pominięte) — w uczelni
    oglądającego (multi-host)."""
    qs = scope_import_do_uczelni(
        MultipleWorksImport.objects.prefetch_related("entries"), request
    )
    return sum(1 for batch in qs if not batch.progress["done"])


def _polish_plural(n: int, one: str, few: str, many: str) -> str:
    """Polska odmiana rzeczownika po liczebniku (1 / 2-4 / 5+, z wyjątkiem
    "nastek" 12-14, które biorą formę "many" mimo końcówki 2-4)."""
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def _landing_context(request):
    """Kontekst kafelkowej strony głównej importera: lista dostawców danych
    (z ikoną i krótkim podpisem „co i skąd") oraz licznik importów w toku
    (pojedynczych sesji + paczek) do slim-baru pod kafelkami."""
    count = _in_progress_sessions_count(request) + _in_progress_batches_count(request)
    return {
        "providers": list(get_providers_metadata().values()),
        "in_progress_count": count,
        "in_progress_label": _polish_plural(count, "import", "importy", "importów"),
    }
