import json

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.urls import NoReverseMatch, reverse
from django.views.generic import FormView, View
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema
from djangoql.serializers import SuggestionsAPISerializer
from djangoql.views import SuggestionsAPIView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord

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


class WprowadzanieDanychOrSuperuserMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Dostep dla superuserow lub uzytkownikow w grupie 'wprowadzanie danych'
    bedacych jednoczesnie w staffie."""

    raise_exception = True

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return (
            user.is_staff and user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
        )


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
        return ctx

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if "query" in request.GET and form.is_valid() and form.cleaned_data["query"]:
            return self.render_results(form)
        return self.render_to_response(self.get_context_data(form=form))

    def render_results(self, form):
        model_key = form.cleaned_data["model"]
        query = form.cleaned_data["query"].strip()
        model = MODELS[model_key]
        queryset = model.objects.all()
        error = None
        results_page = None
        count = None

        try:
            queryset = apply_search(queryset, query)
            count = queryset.count()
            paginator = Paginator(queryset, self.paginate_by)
            page_number = self.request.GET.get("page") or 1
            results_page = paginator.get_page(page_number)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            error = self._format_error(exc)

        if results_page is not None and model_key == MODEL_REKORD:
            self._attach_admin_urls(results_page)

        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=error,
            model_key=model_key,
            query=query,
        )
        return self.render_to_response(context)

    @staticmethod
    def _format_error(exc):
        if isinstance(exc, ValidationError):
            return "; ".join(exc.messages)
        return str(exc)

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
        schema = DjangoQLSchema(model)
        payload = SuggestionsAPISerializer(suggestions_url).serialize(schema)
        return HttpResponse(
            content=json.dumps(payload),
            content_type="application/json; charset=utf-8",
        )


class ZapytanieSuggestionsView(WprowadzanieDanychOrSuperuserMixin, View):
    def get(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        view = SuggestionsAPIView.as_view(schema=DjangoQLSchema(model))
        return view(request)
