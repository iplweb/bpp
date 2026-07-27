import json
from typing import NamedTuple
from urllib.parse import quote, urlencode

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import NoReverseMatch, reverse
from django.views.generic import FormView, View
from djangoql.breakdown import explain
from djangoql.exceptions import DjangoQLError
from djangoql.formatter import format_query
from djangoql.queryset import apply_search
from djangoql.serializers import SuggestionsAPISerializer
from djangoql.views import SuggestionsAPIView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.djangoql_errors import (
    error_location as _error_location,
)
from bpp.djangoql_errors import (
    error_payload as _error_payload,
)
from bpp.djangoql_errors import (
    format_error_text as _format_error_text,
)
from bpp.djangoql_schema import BppQLSchemaOgraniczony
from bpp.models import Autor
from bpp.models.cache import Rekord
from bpp.views.multiseek_export import (
    MULTISEEK_RENDER_LIST_FIELDS,
    MULTISEEK_RENDER_TABLE_FIELDS,
    TABLE_REPORT_TYPES,
)

# Alias zgodności: schemat przeniesiony do bpp.djangoql_schema (wspólny trzon
# dla widoku i adminów). Widok i testy odwołują się do BppZapytanieSchema.
# Widok „Szukaj zapytaniem" używa ograniczonego (allow-lista) schematu —
# autocomplete/zapytania tylko po modelach bibliograficznych. Adminy zostają
# na pełnym BppQLSchema.
BppZapytanieSchema = BppQLSchemaOgraniczony

MODEL_REKORD = "rekord"
MODEL_AUTOR = "autor"

MODEL_CHOICES = (
    (MODEL_REKORD, "Rekord"),
    (MODEL_AUTOR, "Autor"),
)

MODELS = {
    MODEL_REKORD: Rekord,
    MODEL_AUTOR: Autor,
}

# Wartości "postac" to identyfikatory ReportType z multiseek_registry.reports
# (list/table/pkt_wewn/pkt_wewn_bez/bibtex/pivot) — NIE polskie etykiety.
# "rekordy" to jedyna postać własna tej strony (bez odpowiednika w multiseeku).
POSTAC_REKORDY = "rekordy"
# "pivot" — tabela krzyżowa (render przez multiseek/report-body-pivot.html,
# reużyty bez zmian dla logiki, patrz _pivot_context). Rejestr wymiarów/metryk
# rozgałęzia się po modelu przez bpp.pivot.wybierz_rejestr_pivota: rekord ma
# swój od Zadania 6, autor (baza kadrowa K) od Zadania 9. Zasada tego widoku
# zostaje: opcja w <select> albo działa, albo jej nie ma — teraz działa dla
# obu modeli.
POSTAC_PIVOT = "pivot"

POSTACIE_REKORD = (
    (POSTAC_REKORDY, "rekordy (ID + akcje)"),
    ("list", "lista"),
    ("table", "tabela"),
    ("pkt_wewn", "punktacja z wewnętrzną"),
    ("pkt_wewn_bez", "punktacja sumaryczna"),
    ("bibtex", "BibTeX"),
    (POSTAC_PIVOT, "tabela krzyżowa"),
)
POSTACIE_AUTOR = (
    (POSTAC_REKORDY, "autorzy (ID + akcje)"),
    (POSTAC_PIVOT, "tabela krzyżowa"),
)


def postacie_dla_modelu(model_key):
    return POSTACIE_AUTOR if model_key == MODEL_AUTOR else POSTACIE_REKORD


def eksport_formaty(model_key, postac):
    """Formaty eksportu sensowne dla danego modelu i postaci wyniku.

    Model "autor" zwraca CSV/XLSX niezależnie od postaci: macierz
    (postac="pivot") idzie przez _eksport_pivota i naprawdę działa od
    Zadania 9 (bpp.pivot.autor + wybierz_rejestr_pivota); lista autorów
    (postac="rekordy", domyślna) idzie przez autor_csv_export_response /
    autor_xlsx_export_response i naprawdę działa od Zadania 11
    (zapytanie_export.py) — obie ścieżki realne, więc pasek pokazuje linki
    dla obu.

    UWAGA: przy postac="pivot" górny pasek eksportu NIE renderuje się wcale
    (zapytanie.html) — macierz eksportuje własny pasek pod tabelą, bo tylko
    on niesie pivot_row/pivot_col/pivot_val. Gałąź POSTAC_PIVOT niżej zostaje
    jako jedno miejsce opisujące, co endpoint eksportu przyjmuje dla tej
    kombinacji (dane tak, dokument nie).
    """
    if model_key == MODEL_AUTOR:
        return (("csv", "CSV"), ("xlsx", "XLSX"))
    formaty = [("csv", "CSV"), ("xlsx", "XLSX")]
    if postac == POSTAC_PIVOT:
        # Pivot nie ma jeszcze partiala dokumentu (patrz komentarz przy
        # POSTAC_PIVOT) — html/docx/bib zostają na później, dane (csv/xlsx)
        # już mają sens, bo eksport danych nie przechodzi przez partial.
        return tuple(formaty)
    formaty += [("html", "HTML"), ("docx", "DOCX")]
    if postac == "bibtex":
        formaty.append(("bib", "BibTeX (.bib)"))
    return tuple(formaty)


def parse_postac(GET, model_key):
    """Postać wyniku z GET-a, z cichą degradacją do domyślnej.

    Cicha degradacja (nie 400), bo postać przychodzi z linku/zakładki, a
    zmiana modelu w formularzu może unieważnić wcześniejszy wybór — user nie
    ma wtedy nic złego na sumieniu.
    """
    dozwolone = {key for key, _ in postacie_dla_modelu(model_key)}
    postac = GET.get("postac") or POSTAC_REKORDY
    return postac if postac in dozwolone else POSTAC_REKORDY


class WynikZapytania(NamedTuple):
    """Queryset albo błąd — jedno źródło prawdy dla strony i eksportu."""

    queryset: object | None
    error: str | None
    error_location: dict | None


def wykonaj_zapytanie(model_key, query):
    """Zamienia zapytanie DjangoQL na queryset wskazanego modelu.

    Wydzielone z ZapytanieView.render_results, żeby eksport liczył DOKŁADNIE
    ten sam zbiór co strona — łącznie z .distinct(), bez którego filtr po
    relacji "do wielu" (np. autorzy.autor.nazwisko) zwielokrotniłby rekord
    raz na każdy pasujący wiersz powiązany.
    """
    model = MODELS[model_key]
    try:
        queryset = apply_search(
            model.objects.all(), query, schema=BppZapytanieSchema
        ).distinct()
    except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
        line, column, mark = _error_location(exc, query)
        location = (
            {"line": line, "column": column, "mark": mark} if line and column else None
        )
        return WynikZapytania(None, _format_error_text(exc), location)
    return WynikZapytania(queryset, None, None)


# Przyklady zapytan renderowane w sekcji pomocy. Wszystkie SA testowane na
# poprawnosc skladniowa przez DjangoQLParser (test_zapytanie_examples_parseable).
# UWAGA: DjangoQL grammar NIE WSPIERA unary `not (expression)` — `NOT` jest
# tylko modyfikatorem dla `NOT STARTSWITH`, `NOT ENDSWITH`, `NOT IN`. Do negacji
# uzywaj `!=`, `!~`, `not startswith`, `not endswith`, `not in`.
EXAMPLES = [
    {
        "level": 1,
        "title": "Podstawowe",
        "subtitle": "jeden, dwa warunki",
        "groups": [
            {
                "model": MODEL_REKORD,
                "label": "Rekord",
                "items": [
                    ("", 'tytul_oryginalny ~ "nowotwor"'),
                    ("", "rok = 2024"),
                    ("", "rok >= 2022 and rok <= 2024"),
                    ("", 'charakter_formalny.skrot = "AC"'),
                    ("", 'tytul_oryginalny ~ "covid" and rok = 2023'),
                    ("", 'doi != ""'),
                    ("Po autorze (autocomplete)", 'autorzy.autor__rel = "Kowalski"'),
                    (
                        "Po jednostce (autocomplete)",
                        'autorzy.jednostka__rel = "Kardiologii"',
                    ),
                ],
            },
            {
                "model": MODEL_AUTOR,
                "label": "Autor",
                "items": [
                    ("", 'nazwisko ~ "Kowal"'),
                    ("", 'tytul.skrot = "prof."'),
                    ("", 'nazwisko = "Kowalski" and imiona = "Jan"'),
                    ("", 'orcid != ""'),
                    ("", 'aktualna_jednostka.nazwa ~ "Medycyny"'),
                    ("Po tytule (autocomplete)", 'tytul__rel = "prof."'),
                    (
                        "Po jednostce (autocomplete)",
                        'aktualna_jednostka__rel = "Kardiologii"',
                    ),
                ],
            },
        ],
    },
    {
        "level": 2,
        "title": "Srednie",
        "subtitle": "wiele warunkow, relacje, listy in (...)",
        "groups": [
            {
                "model": MODEL_REKORD,
                "label": "Rekord",
                "items": [
                    (
                        "Wysoko punktowane prace ostatnich trzech lat",
                        "rok >= 2022 and punkty_kbn >= 100",
                    ),
                    (
                        "Wysoki Impact Factor z zakresu lat",
                        "impact_factor > 5 and rok in (2022, 2023, 2024)",
                    ),
                    (
                        "Brak DOI mimo wysokiej punktacji (do uzupelnienia)",
                        'punkty_kbn >= 70 and doi = ""',
                    ),
                    (
                        "Czesto cytowane, ale nierecenzowane",
                        "liczba_cytowan > 10 and recenzowana = False",
                    ),
                    (
                        "Konkretny charakter + zakres punktow",
                        'charakter_formalny.skrot = "AC" and punkty_kbn >= 40 '
                        "and punkty_kbn <= 100",
                    ),
                    (
                        "Konkretne zrodlo + lata",
                        'zrodlo.nazwa ~ "Nature" and rok >= 2020',
                    ),
                    (
                        "Polskojezyczne artykuly",
                        'jezyk.skrot = "pol" and charakter_formalny.skrot = "AC"',
                    ),
                    (
                        "Open Access z ostatnich lat",
                        "openaccess_tryb_dostepu != None and rok >= 2023",
                    ),
                    (
                        "Slowa kluczowe w tytule (combo OR)",
                        'tytul_oryginalny ~ "COVID" or tytul_oryginalny ~ "SARS-CoV"',
                    ),
                    (
                        "Rekordy bez WWW i bez DOI (do redakcji)",
                        'www = "" and doi = "" and rok >= 2023',
                    ),
                ],
            },
            {
                "model": MODEL_AUTOR,
                "label": "Autor",
                "items": [
                    (
                        "Profesorowie z wpisanym ORCID",
                        'tytul.skrot = "prof." and orcid != ""',
                    ),
                    (
                        "Maja ORCID ale brak go w PBN",
                        'orcid != "" and orcid_w_pbn = False',
                    ),
                    (
                        "Z konkretnej jednostki (LIKE po nazwie)",
                        'aktualna_jednostka.nazwa ~ "Medycyny" and '
                        'tytul.skrot startswith "dr"',
                    ),
                    (
                        "Brak emaila, ale jest ORCID",
                        'email = "" and orcid != ""',
                    ),
                    (
                        "Konkretna jednostka po skrocie + filtr po nazwisku",
                        'nazwisko startswith "Now" and '
                        'aktualna_jednostka.skrot = "II WL"',
                    ),
                    (
                        "Doktoraty + asystenci (zbior tytulow)",
                        'tytul.skrot in ("dr", "dr hab.", "mgr")',
                    ),
                ],
            },
        ],
    },
    {
        "level": 3,
        "title": "Zaawansowane",
        "subtitle": "grupowanie nawiasami, negacja, zlozone audyty",
        "groups": [
            {
                "model": MODEL_REKORD,
                "label": "Rekord",
                "items": [
                    (
                        "Audyt ewaluacyjny — tylko recenzowane, z DOI, "
                        "w okresie 2022–2025, min. 70 pkt",
                        'recenzowana = True and doi != "" and '
                        "rok in (2022, 2023, 2024, 2025) and punkty_kbn >= 70",
                    ),
                    (
                        "Grupowanie (rok OR + charakter OR) × punktacja",
                        "(rok = 2024 or rok = 2025) and "
                        '(charakter_formalny.skrot = "AC" or '
                        'charakter_formalny.skrot = "AOR") and punkty_kbn >= 100',
                    ),
                    (
                        "Negacja: wszystko poza artykulami z czasopism, IF>=3, od 2023",
                        'charakter_formalny.skrot != "AC" and rok >= 2023 '
                        "and impact_factor > 3",
                    ),
                    (
                        "Wieloklauzulowo: tytul × jezyk × liczba autorow × rok",
                        '(tytul_oryginalny ~ "COVID" or tytul_oryginalny ~ "SARS") '
                        'and jezyk.skrot in ("ang", "pol") and '
                        "liczba_autorow >= 3 and rok = 2023",
                    ),
                    (
                        "Wydawcy Elsevier/Springer/Wiley + przedzial punktow",
                        '(wydawca.nazwa ~ "Elsevier" or wydawca.nazwa ~ "Springer" '
                        'or wydawca.nazwa ~ "Wiley") and rok >= 2022 '
                        "and punkty_kbn >= 70 and punkty_kbn <= 200",
                    ),
                    (
                        "Hot & trending: cytowane >50 razy w okresie, IF>5",
                        "liczba_cytowan > 50 and rok >= 2020 and impact_factor > 5",
                    ),
                    (
                        "Audyt jakosci danych — artykuly 2024+ bez DOI/WWW",
                        'charakter_formalny.skrot = "AC" and rok >= 2024 '
                        'and doi = "" and www = "" and recenzowana = True',
                    ),
                    (
                        "Top-tier OA z Nature/Cell/Science/Lancet",
                        'zrodlo.nazwa in ("Nature", "Cell", "Science", '
                        '"The Lancet") and rok > 2020 and '
                        "openaccess_tryb_dostepu != None",
                    ),
                    (
                        "Zmienione od poczatku roku z adnotacjami",
                        'ostatnio_zmieniony >= "2025-01-01" and adnotacje != ""',
                    ),
                    (
                        "Wielowarunkowa granica IF + zakres punktow + minimum cytowan",
                        "impact_factor >= 5 and impact_factor <= 10 and "
                        "punkty_kbn >= 100 and liczba_cytowan >= 5",
                    ),
                ],
            },
            {
                "model": MODEL_AUTOR,
                "label": "Autor",
                "items": [
                    (
                        "Profesorowie z jednostki + ORCID + brak w PBN",
                        'tytul.skrot in ("prof.", "prof. dr hab.") and '
                        'aktualna_jednostka.skrot startswith "I WL" and '
                        'orcid != "" and orcid_w_pbn = False',
                    ),
                    (
                        "Dwie jednostki + tytul dr/dr hab. + jest orcid",
                        '(aktualna_jednostka.skrot = "II WL" or '
                        'aktualna_jednostka.skrot = "WLS") and '
                        'tytul.skrot startswith "dr" and orcid != ""',
                    ),
                    (
                        "Brak emaila ale jest ORCID (do uzupelnienia kontaktu)",
                        'email = "" and orcid != "" and '
                        'tytul.skrot in ("dr", "dr hab.", "prof.")',
                    ),
                    (
                        "Format ORCID nieprawidlowy (nie zaczyna sie od '0000-')",
                        'orcid != "" and orcid not startswith "0000-"',
                    ),
                    (
                        "Wszystkie z aktualna jednostka, oprocz mgr/mgr inz.",
                        "aktualna_jednostka != None and "
                        'tytul.skrot not in ("mgr", "mgr inz.")',
                    ),
                ],
            },
        ],
    },
]


# Presety pivota autorskiego — skróty do gotowych tabel krzyżowych w sekcji
# pomocy. Pierwsze cztery korzystają z bazy kadrowej K (liczba autorów),
# pozostałe z baz bibliometrycznych: P (liczba prac) i U (Σ slotów, Σ pkdaut).
# KAŻDA para (wymiar, metryka) musi być poprawna dla bazy tej metryki —
# wymiar publikacyjny (rok, dyscyplina) NIE istnieje w bazie K i
# parse_pivot_params_autor cicho zamieniłby go na domyślny, dając preset
# pokazujący nie to, co obiecuje etykieta.
PIVOT_PRESETY_AUTOR = (
    ("Struktura kadrowa", "jednostka", "tytul", "liczba_autorow"),
    ("Audyt kompletności ORCID", "jednostka", "ma_orcid", "liczba_autorow"),
    ("Gotowość do PBN", "jednostka", "ma_pbn_uid", "liczba_autorow"),
    ("Struktura płci wg tytułów", "tytul", "plec", "liczba_autorow"),
    ("Produktywność jednostek", "jednostka", "rok", "liczba_prac"),
    ("Ranking autorów (slotowy)", "autor", "rok", "suma_slotow"),
    ("Udziały dyscyplinowe", "dyscyplina", "rok", "suma_slotow"),
    ("Wkład punktowy jednostek", "jednostka", "rok", "suma_pkdaut"),
)


def pivot_presety_dla_modelu(model_key, query):
    """Skróty do gotowych tabel krzyżowych, renderowane w sekcji pomocy —
    ten sam wzorzec co EXAMPLES dla zapytań DjangoQL.

    `query` to WYSŁANE zapytanie DjangoQL z GET-a — presety mają DOŁOŻYĆ wybór
    wymiarów/metryki do zapytania, jakie user już wysłał, nie zgubić go (klik
    w preset ma pokazać macierz DLA BIEŻĄCEGO zawężenia).

    Lista jest zwracana niezależnie od tego, czy zapytanie już poszło —
    natomiast szablon renderuje ją jako KLIKALNE linki tylko wtedy, gdy
    `query` jest niepuste. Bez zapytania preset nie ma czego dokładać: puste
    zapytanie nie przechodzi przez parser DjangoQL („Unexpected end of
    input"), więc `ZapytanieView.get` w ogóle nie wchodzi w `render_results`
    i taki link przeładowałby stronę bez żadnego efektu i bez komunikatu.
    Zamiast martwego linku szablon pokazuje wtedy same nazwy presetów plus
    zdanie, co trzeba zrobić, żeby ożyły.

    `safe="/"` w urlencode() dobrany tak, żeby zakodowana wartość `query`
    zgadzała się bajt-w-bajt z tym, co produkuje filtr szablonowy
    `|urlencode` (Django: quote(value, safe='/') gdy `safe` nie podano) —
    ta sama para znaków bezpiecznych, żeby test na obecność zakodowanego
    zapytania w linku presetu nie zależał od przypadkowej zgodności dwóch
    niezależnych implementacji urlencode.
    """
    if model_key != MODEL_AUTOR:
        return ()
    presety = []
    for opis, row, col, metric in PIVOT_PRESETY_AUTOR:
        qs = urlencode(
            {
                "model": MODEL_AUTOR,
                "query": query,
                "postac": POSTAC_PIVOT,
                "pivot_row": row,
                "pivot_col": col,
                "pivot_val": metric,
            },
            quote_via=quote,
            safe="/",
        )
        presety.append({"opis": opis, "query": qs})
    return tuple(presety)


def user_can_use_query_editor(user):
    """Czy user widzi/uzywa edytora zapytan DjangoQL.

    Superuser, albo staff w grupie 'wprowadzanie danych'. Jedno zrodlo
    prawdy dla: mixinu widoku, endpointu konwertera i filtru szablonowego.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.is_staff and user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


class WprowadzanieDanychOrSuperuserMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Dostep dla superuserow lub uzytkownikow w grupie 'wprowadzanie danych'
    bedacych jednoczesnie w staffie."""

    raise_exception = True

    def test_func(self):
        return user_can_use_query_editor(self.request.user)


class ZapytanieForm(forms.Form):
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        widget=forms.RadioSelect,
        initial=MODEL_REKORD,
        label="Model do przeszukania",
    )
    query = forms.CharField(
        label="Zapytanie DjangoQL",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": ('tytul_oryginalny ~ "nowotwor" and rok >= 2020'),
                "spellcheck": "false",
                "autocomplete": "off",
                # `djangoql` -> multiline.js wpina Shift+Enter; nakładkę
                # highlight.js doczepiamy jawnie w zapytanie.js (po uchwyt).
                "class": "djangoql",
            }
        ),
        required=False,
        help_text=(
            "Skladnia DjangoQL: pole operator wartosc, laczone przez "
            "<code>and</code> / <code>or</code>. "
            "Operatory: <code>=</code>, <code>!=</code>, <code>&gt;</code>, "
            "<code>&gt;=</code>, <code>&lt;</code>, <code>&lt;=</code>, "
            "<code>~</code> (zawiera), <code>!~</code> (nie zawiera), "
            "<code>in</code>, <code>not in</code>. "
            "Stringi w cudzyslowach. "
            'Przyklady: <code>tytul_oryginalny ~ "rak"</code>, '
            '<code>rok = 2024 and charakter_formalny.skrot = "AC"</code>, '
            '<code>nazwisko ~ "Kowal" or imiona ~ "Jan"</code>.'
        ),
    )


class ZapytanieView(WprowadzanieDanychOrSuperuserMixin, FormView):
    template_name = "bpp/zapytanie.html"
    form_class = ZapytanieForm
    paginate_by = 25

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET" and "model" in self.request.GET:
            kwargs["data"] = self.request.GET
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("examples", EXAMPLES)
        # model_key nie jest jeszcze w kontekscie przed pierwszym szukaniem
        # (render_results go dokłada) — spadamy do GET-a/domyślnego modelu,
        # żeby pasek "Postać wyniku" pokazywał sensowne opcje od pierwszego
        # wyrenderowania strony, nie tylko po wynikach.
        model_key = ctx.get("model_key")
        if model_key not in MODELS:
            model_key = self.request.GET.get("model", MODEL_REKORD)
            if model_key not in MODELS:
                model_key = MODEL_REKORD
        ctx.setdefault("postac", parse_postac(self.request.GET, model_key))
        ctx.setdefault("postacie", postacie_dla_modelu(model_key))
        ctx.setdefault(
            "pivot_presety",
            pivot_presety_dla_modelu(model_key, self.request.GET.get("query", "")),
        )
        return ctx

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if "query" in request.GET and form.is_valid() and form.cleaned_data["query"]:
            return self.render_results(form)
        return self.render_to_response(self.get_context_data(form=form))

    def render_results(self, form):
        model_key = form.cleaned_data["model"]
        query = form.cleaned_data["query"].strip()
        postac = parse_postac(self.request.GET, model_key)
        wynik = wykonaj_zapytanie(model_key, query)
        results_page = None
        count = None
        sumy = None

        if wynik.queryset is not None:
            count = wynik.queryset.count()
            # Projekcja dostrojona do partiala renderu (jak w
            # document_export_response) — bez niej strona ciągnie CAŁY
            # rekord (N+1 na charakter_formalny/typ_kbn na każdym wierszu).
            # "rekordy"/"pivot" trzymają dzisiejszą tabelę/placeholder bez
            # zmian, więc queryset zostaje nietkniety.
            queryset_do_widoku = wynik.queryset
            if model_key == MODEL_REKORD and postac in TABLE_REPORT_TYPES:
                queryset_do_widoku = queryset_do_widoku.select_related(
                    "charakter_formalny", "typ_kbn"
                ).only(*MULTISEEK_RENDER_TABLE_FIELDS)
            elif model_key == MODEL_REKORD and postac not in (
                POSTAC_REKORDY,
                POSTAC_PIVOT,
            ):
                # Obejmuje "list" (report-body-list.html) i "bibtex"
                # (report-body-bibtex.html). Ta druga woła
                # element.original.to_bibtex — "original" dociąga PEŁNY
                # obiekt publikacji OSOBNYM zapytaniem po polu "id" (tuple
                # content_type_id+object_id, czyli composite PK Rekordu).
                # .only() na Rekordzie nie ma na to wpływu: "id" jest PK-iem,
                # więc Django go dociąga zawsze, niezależnie od projekcji.
                queryset_do_widoku = queryset_do_widoku.only(
                    *MULTISEEK_RENDER_LIST_FIELDS
                )
            paginator = Paginator(queryset_do_widoku, self.paginate_by)
            page_number = self.request.GET.get("page") or 1
            results_page = paginator.get_page(page_number)

        if results_page is not None and model_key == MODEL_REKORD:
            self._attach_admin_urls(results_page)

        if postac in TABLE_REPORT_TYPES and wynik.queryset is not None:
            # Sumy liczone po CAŁYM zbiorze wyników, nie po stronie —
            # inaczej "Suma:" w stopce tabeli myłaby redaktora przy
            # zapytaniach z wieloma stronami.
            sumy = wynik.queryset.aggregate(
                Sum("impact_factor"),
                Sum("liczba_cytowan"),
                Sum("punkty_kbn"),
                Sum("punktacja_wewnetrzna"),
            )

        pivot_ctx = {}
        if postac == POSTAC_PIVOT and wynik.queryset is not None:
            pivot_ctx = self._pivot_context(model_key, wynik.queryset)

        # Rozbicie „dlaczego 0 wyników" pokazuje (z podświetlaniem składni) panel
        # „Wyjaśnij liczby" w JS — auto-otwierany, gdy count == 0 (patrz
        # autoExplain w szablonie + zapytanie.js). Serwer nie renderuje już
        # własnego rozbicia.
        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=wynik.error,
            error_location=wynik.error_location,
            model_key=model_key,
            query=query,
            postac=postac,
            postacie=postacie_dla_modelu(model_key),
            sumy=sumy,
            eksport_formaty=eksport_formaty(model_key, postac),
            **pivot_ctx,
        )
        return self.render_to_response(context)

    def _pivot_context(self, model_key, queryset):
        """Kontekst tabeli krzyżowej — klucze zgodne z multiseekiem, żeby
        partial report-body-pivot.html renderował się bez zmian.

        Dokłada też trzy klucze, które report-body-pivot.html potrzebuje
        DODATKOWO na tej stronie (P1-P3 z brief'u): multiseek trzyma filtr
        w sesji i renderuje partial pod /multiseek/results/, więc jego
        domyślne wartości (form action=".", linki "../export/") nie
        przenoszą stanu strony zapytania (model/query/postac żyją w URL-u)
        i nie trafiają pod właściwy prefiks eksportu.

        Rejestr wymiarów/metryk (rekord vs autor) wybiera
        `wybierz_rejestr_pivota` — JEDYNE miejsce w widoku, które rozgałęzia
        się po modelu (eksport, `ZapytanieExportView._eksport_pivota`, woła
        ten sam helper).

        `pivot_dimensions` w kontekście to już PRZEFILTROWANY słownik — tylko
        wymiary dostępne w bazie agregacji wybranej metryki
        (`dim.expr_dla(metric.baza) is not None`). Partial iteruje ten
        słownik ślepo i nic nie wie o bazach K/P/U; dla rejestru rekordowego
        `expr` jest zwykłym stringiem, więc `expr_dla()` zawsze zwraca
        ścieżkę i filtr nic nie usuwa (zachowanie multiseeka bez zmian).
        """
        from bpp.pivot import core as pivot_core
        from bpp.pivot import wybierz_rejestr_pivota

        rejestr = wybierz_rejestr_pivota(model_key)
        row_dim, col_dim, metric = rejestr.parse_params(self.request.GET)
        dostepne_wymiary = {
            key: dim
            for key, dim in rejestr.DIMENSIONS.items()
            if dim.expr_dla(metric.baza) is not None
        }
        ctx = {
            "pivot_dimensions": dostepne_wymiary,
            "pivot_metrics": rejestr.METRICS,
            "pivot_row_dim": row_dim,
            "pivot_col_dim": col_dim,
            "pivot_metric": metric,
            "pivot_form_action": reverse("bpp:zapytanie"),
            "pivot_form_hidden": [
                ("model", model_key),
                ("query", self.request.GET.get("query", "")),
                ("postac", POSTAC_PIVOT),
            ],
            "pivot_export_base": reverse(
                "bpp:zapytanie_eksport", kwargs={"export_format": "csv"}
            ).rsplit("csv/", 1)[0],
        }
        try:
            ctx["pivot"] = rejestr.zbuduj(queryset, row_dim, col_dim, metric)
        except pivot_core.PivotTooLargeError as exc:
            ctx["pivot"] = None
            ctx["pivot_error"] = exc
        return ctx

    @staticmethod
    def _attach_admin_urls(results_page):
        """Dla kazdego Rekord-u w wynikach prebuiluje obj.admin_url.

        rekord.pk to tuple (content_type_id, object_id) — odsylamy do
        admina konkretnego podtypu (Wydawnictwo_Ciagle, Patent itd.).
        ContentType.objects.get_for_id jest cached w pamieci procesu,
        wiec narzut na strone = 0 DB queries po pierwszym uzyciu danego
        ct_id.
        """
        for obj in results_page:
            try:
                ct = ContentType.objects.get_for_id(obj.pk[0])
                obj.admin_url = reverse(
                    f"admin:{ct.app_label}_{ct.model}_change",
                    args=[obj.pk[1]],
                )
            except (ContentType.DoesNotExist, NoReverseMatch):
                obj.admin_url = None


def _resolve_model_or_404(model_key):
    try:
        return MODELS[model_key]
    except KeyError:
        raise Http404(f"Nieznany model: {model_key}") from None


class ZapytanieIntrospectView(WprowadzanieDanychOrSuperuserMixin, View):
    def get(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        suggestions_url = reverse(
            "bpp:zapytanie_suggestions", kwargs={"model_key": model_key}
        )
        schema = BppZapytanieSchema(model)
        payload = SuggestionsAPISerializer(suggestions_url).serialize(schema)
        return HttpResponse(
            content=json.dumps(payload),
            content_type="application/json; charset=utf-8",
        )


class ZapytanieSuggestionsView(WprowadzanieDanychOrSuperuserMixin, View):
    def get(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        view = SuggestionsAPIView.as_view(schema=BppZapytanieSchema(model))
        return view(request)


def _query_param(request):
    return (request.POST.get("q") or request.GET.get("q") or "").strip()


class _ZapytanieAjaxView(WprowadzanieDanychOrSuperuserMixin, View):
    """Baza AJAX-owych endpointów zapytania (format/explain).

    Wspólny odczyt ``q`` (POST z JS, GET dla curl/testów) i obsługa błędu jako
    JSON 400 z koordynatami do podświetlenia. Reużywa „nie-publicznych"
    prymitywów djangoql (formatter/breakdown) zamiast własnej logiki."""

    def get(self, request, model_key):
        return self.handle(request, model_key)

    def post(self, request, model_key):
        return self.handle(request, model_key)

    def handle(self, request, model_key):  # pragma: no cover - abstrakcyjna
        raise NotImplementedError


class ZapytanieFormatView(_ZapytanieAjaxView):
    """Pretty-print zapytania przez ``djangoql.formatter.format_query``.

    ``{"formatted": "<wcięte, wieloliniowe zapytanie>"}`` albo ``400
    {"error", "line", "column", "mark"}``."""

    def handle(self, request, model_key):
        _resolve_model_or_404(model_key)
        query = _query_param(request)
        if not query:
            return JsonResponse({"formatted": ""})
        try:
            return JsonResponse({"formatted": format_query(query)})
        except DjangoQLError as exc:
            return JsonResponse(_error_payload(exc, query), status=400)


class ZapytanieExplainView(_ZapytanieAjaxView):
    """Rozbicie zapytania na drzewo liczności gałęzi przez
    ``djangoql.breakdown.explain`` — na żądanie, dla DOWOLNEGO zapytania (nie
    tylko zerowego).

    ``{"tree": {text, count, role, children}}`` albo ``400 {"error", …}``."""

    def handle(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        query = _query_param(request)
        if not query:
            return JsonResponse({"tree": None})
        try:
            tree = explain(model.objects.all(), query, schema=BppZapytanieSchema)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            return JsonResponse(_error_payload(exc, query), status=400)
        return JsonResponse({"tree": tree})
