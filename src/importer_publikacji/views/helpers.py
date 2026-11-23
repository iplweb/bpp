"""Pomocnicze funkcje i stałe wspólne dla wszystkich kroków wizarda.

Zawiera:
- ścieżki szablonów partiali HTMX,
- wykrywanie języka tytułu (heurystyka + langdetect),
- mapowanie typu publikacji CrossRef → BPP,
- kontekst dla kroku fetch / listy sesji,
- pomocnicze nakładki HTMX (HX-Push-Url, OOB breadcrumbs).
"""

from datetime import date
from urllib.parse import urlencode

from django import forms
from django.db.models import Q
from django.shortcuts import render
from django.template.loader import render_to_string

from bpp.models import Crossref_Mapper

from ..forms import STATUS_UTKNIETE, FetchForm, SessionFilterForm
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
BATCH_DETAIL_DOI = "importer_publikacji/partials/batch_detail_doi.html"
STEP_WIELE_DOI = "importer_publikacji/partials/step_wiele_doi.html"
BREADCRUMBS_OOB = "importer_publikacji/partials/_breadcrumbs_oob.html"

# Sortowanie listy sesji: pole ORM → etykieta kolumny (w komunikacie
# o zapamiętanym widoku, FD#615). Kolumny tabeli niosą ``data-sort-key``
# z tymi samymi kluczami — klik w nagłówek odsyła je w parametrze ``sort``.
SESSIONS_SORT_LABELS = {
    "created": "Data",
    "normalized_data__title": "Tytuł",
    "normalized_data__doi": "DOI / Identyfikator",
    "provider_name": "Źródło",
    "status": "Status",
    "created_by__username": "Utworzył",
    "modified_by__username": "Zmodyfikował",
}
SESSIONS_ALLOWED_SORTS = {
    klucz for pole in SESSIONS_SORT_LABELS for klucz in (pole, f"-{pole}")
}
SESSIONS_DEFAULT_SORT = "-created"

# Parametry GET filtrów listy sesji — tylko te trafiają do adresu URL
# i do zapamiętanego widoku w sesji użytkownika (FD#615).
SESSIONS_FILTER_KEYS = (
    "date_from",
    "date_to",
    "title",
    "doi",
    "provider_name",
    "status",
    "etap_bledu",
    "rekord",
    "paczka",
    "created_by",
    "modified_by",
)
# Klucz w ``request.session`` z ostatnim zestawem filtrów i sortowania.
SESSIONS_SAVED_VIEW_KEY = "importer_publikacji_lista_sesji"


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


def _kontekst_wejscia_qs(zgloszenie=None, zgloszenia_filtry=None, identifier=None):
    """Querystring kontekstu, z którym operator wszedł do importera.

    ``zgloszenie`` (wiązanie, FD#443), ``zgloszenia_filtry`` (powrót do
    listy zgłoszeń, FD#482) i ``identifier`` muszą przeżyć przeskoki
    „Wybierz inne źródło" → kafelek. Jeden ciąg, budowany tutaj, zamiast
    sklejania parametrów warunkami w szablonach — tam właśnie gubiło się
    wiązanie ze zgłoszeniem. Puste wartości pomijamy.
    """
    pary = [
        ("zgloszenie", zgloszenie),
        ("zgloszenia_filtry", zgloszenia_filtry),
        ("identifier", identifier),
    ]
    return urlencode([(k, v) for k, v in pary if v])


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
        "kontekst_qs": _kontekst_wejscia_qs(
            form["zgloszenie"].value(),
            form["zgloszenia_filtry"].value(),
            form["identifier"].value(),
        ),
    }


# Proste filtry listy sesji: pole formularza → lookup ORM.
_SESSIONS_SIMPLE_FILTERS = {
    "date_from": "created__date__gte",
    "date_to": "created__date__lte",
    "title": "normalized_data__title__icontains",
    "doi": "normalized_data__doi__icontains",
    "provider_name": "provider_name",
    "created_by": "created_by",
    "modified_by": "modified_by",
    "etap_bledu": "last_failed_stage",
    "paczka": "batch_entry__parent_id",
}
# Filtr „Rekord wynikowy”: wartość → ``created_record_id__isnull``.
_SESSIONS_REKORD_ISNULL = {"jest": False, "brak": True}


def _apply_session_filters(qs, cleaned_data):
    """Nałóż na queryset filtry z poprawnie zwalidowanego formularza
    (poza statusem — patrz :func:`_apply_status_filter`)."""
    for pole, lookup in _SESSIONS_SIMPLE_FILTERS.items():
        wartosc = cleaned_data.get(pole)
        if wartosc:
            qs = qs.filter(**{lookup: wartosc})
    rekord = cleaned_data.get("rekord")
    if rekord in _SESSIONS_REKORD_ISNULL:
        qs = qs.filter(created_record_id__isnull=_SESSIONS_REKORD_ISNULL[rekord])
    return qs


def _apply_status_filter(qs, statusy):
    """Wybrane statusy łączymy przez „lub”; pseudo-status „utknięte” to
    warunek watchdoga. Bez wyboru — wszystko poza anulowanymi (anulowane
    pokazujemy tylko, gdy ktoś je jawnie wybrał)."""
    if not statusy:
        return qs.exclude(status=ImportSession.Status.CANCELLED)
    warunek = Q(status__in=[s for s in statusy if s != STATUS_UTKNIETE])
    if STATUS_UTKNIETE in statusy:
        warunek |= ImportSession.stalled_q()
    return qs.filter(warunek)


def _sessions_queryset(request, params=None):
    """Zbuduj queryset sesji z filtrami z parametrów GET.

    ``params`` — domyślnie ``request.GET``; widok listy podaje tu zapamiętany
    zestaw filtrów, gdy przywraca widok (FD#615).
    """
    if params is None:
        params = request.GET
    qs = ImportSession.objects.select_related(
        "created_by", "modified_by", "created_record_content_type", "batch_entry"
    ).prefetch_related("created_record")
    # Izolacja multi-host: redaktor widzi tylko sesje swojej uczelni (uwaga #3).
    qs = scope_import_do_uczelni(qs, request)

    form = SessionFilterForm(params)
    # Nieprawidłowe pole (np. stara zakładka z nieistniejącym statusem) nie
    # wyłącza pozostałych filtrów: ``cleaned_data`` zawiera wtedy tylko pola
    # poprawne, a błędy pokazuje szablon.
    form.is_valid()
    qs = _apply_session_filters(qs, form.cleaned_data)
    qs = _apply_status_filter(qs, form.cleaned_data.get("status") or [])

    sort = params.get("sort", SESSIONS_DEFAULT_SORT)
    if sort not in SESSIONS_ALLOWED_SORTS:
        sort = SESSIONS_DEFAULT_SORT
    qs = qs.order_by(sort, "-pk")

    return qs, form, sort


def _sessions_querystring(params, sort):
    """Znormalizowany querystring widoku listy: tylko znane filtry
    z niepustą wartością + sortowanie, jeśli inne niż domyślne."""
    pary = [
        (klucz, wartosc)
        for klucz in SESSIONS_FILTER_KEYS
        for wartosc in params.getlist(klucz)
        if wartosc.strip()
    ]
    if sort != SESSIONS_DEFAULT_SORT:
        pary.append(("sort", sort))
    return urlencode(pary)


def _sessions_filters_description(form, sort):
    """Czytelny opis aktywnych filtrów i sortowania (komunikat o
    przywróconym widoku, FD#615), np. ``["Status: Błąd importu"]``."""
    opis = []
    if form.is_bound:
        form.is_valid()
        for nazwa, pole in form.fields.items():
            wartosc = form.cleaned_data.get(nazwa)
            if wartosc in (None, "", []):
                continue
            if isinstance(pole, forms.ModelChoiceField):
                tekst = wartosc.get_username()
            elif isinstance(pole, forms.ChoiceField):
                etykiety = dict(pole.choices)
                if isinstance(wartosc, list):
                    tekst = ", ".join(str(etykiety.get(w, w)) for w in wartosc)
                else:
                    tekst = str(etykiety.get(wartosc, wartosc))
            elif isinstance(wartosc, date):
                tekst = wartosc.isoformat()
            else:
                tekst = str(wartosc)
            opis.append(f"{pole.label}: {tekst}")
    if sort != SESSIONS_DEFAULT_SORT:
        kierunek = "malejąco" if sort.startswith("-") else "rosnąco"
        opis.append(f"Sortowanie: {SESSIONS_SORT_LABELS[sort.lstrip('-')]}, {kierunek}")
    return opis


def _sessions_list_context(request, params=None):
    """Kontekst listy sesji z filtrami."""
    if params is None:
        params = request.GET
    qs, form, sort = _sessions_queryset(request, params)
    statusy = form.cleaned_data.get("status") or []
    querystring = _sessions_querystring(params, sort)
    return {
        "sessions": qs,
        "filter_form": form,
        "sort": sort,
        "sort_key": sort.lstrip("-"),
        "sort_desc": sort.startswith("-"),
        "sessions_querystring": querystring,
        "aktywne_filtry": bool(_sessions_querystring(params, SESSIONS_DEFAULT_SORT)),
        "tylko_bledy": statusy == [ImportSession.Status.IMPORT_FAILED],
        "status_import_failed": ImportSession.Status.IMPORT_FAILED,
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
        "kontekst_qs": _kontekst_wejscia_qs(
            request.GET.get("zgloszenie"),
            request.GET.get("zgloszenia_filtry"),
            request.GET.get("identifier"),
        ),
    }
