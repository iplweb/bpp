import json
import logging

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, FieldError, ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.http import Http404, HttpResponse
from django.urls import NoReverseMatch, reverse
from django.views.generic import FormView, View
from djangoql.breakdown import explain_empty
from djangoql.exceptions import DjangoQLError
from djangoql.extras import ExtrasSchema
from djangoql.queryset import apply_search
from djangoql.serializers import SuggestionsAPISerializer
from djangoql.views import SuggestionsAPIView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jezyk,
    Kierunek_Studiow,
    Konferencja,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawca,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.models.autor import Tytul
from bpp.models.cache import Autorzy, Rekord
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)

logger = logging.getLogger(__name__)

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


def _dal_picker(lookup_name, url, search_fields):
    """Config pickera ``<fk>__rel`` korzystającego z czystego endpointu DAL."""
    return {
        "lookup_name": lookup_name,
        "url": url,
        "search_fields": list(search_fields),
    }


_VISIBILITY_FIELDS = ("widoczny", "widoczna", "widoczne")


def _visible_qs(model):
    """Queryset modelu z odfiltrowanymi niewidocznymi pozycjami, jeśli model ma
    boolowskie pole ``widoczny``/``widoczna``/``widoczne`` — żeby lookup nie
    podpowiadał ukrytych rekordów. W przeciwnym razie pełny ``all()``.
    """
    for name in _VISIBILITY_FIELDS:
        try:
            field = model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if isinstance(field, models.BooleanField):
            return model.objects.filter(**{name: True})
    return model.objects.all()


def _qs_picker(lookup_name, model, search_fields=("nazwa", "skrot")):
    """Config pickera ``<fk>__rel`` z querysetu modelu — icontains po
    ``search_fields``, ograniczony limitem AutocompleteField. Używane zamiast
    endpointów DAL, które bywają bramkowane grupą albo doklejają opcję „utwórz".
    Niewidoczne pozycje są odfiltrowane (patrz :func:`_visible_qs`).
    """
    return {
        "lookup_name": lookup_name,
        "queryset": _visible_qs(model),
        "search_fields": list(search_fields),
    }


class BppZapytanieSchema(ExtrasSchema):
    """ExtrasSchema z pickerami ``<fk>__rel`` obok trawersacji z kropką.

    Kropka (``autorzy.autor.nazwisko``, ``tytul.skrot``, ``zrodlo.nazwa``)
    zostaje domyślna dla każdego FK. ``<fk>__rel`` to picker: wybierasz obiekt
    z podpowiedzi i filtruje po jego pk (``lookup_name`` = realny FK), z
    fallbackiem free-text (icontains po ``search_fields``). ``autor`` i
    ``jednostka`` używają czystych endpointów DAL; reszta — querysetów
    (bramkowane / „create" endpointy DAL odpadają).
    """

    autocomplete = {
        Autorzy: {
            "autor__rel": _dal_picker(
                "autor", "bpp:public-autor-autocomplete", ["nazwisko", "imiona"]
            ),
            "jednostka__rel": _dal_picker(
                "jednostka", "bpp:jednostka-widoczna-autocomplete", ["nazwa", "skrot"]
            ),
            "dyscyplina_naukowa__rel": _qs_picker(
                "dyscyplina_naukowa", Dyscyplina_Naukowa, ["nazwa", "kod"]
            ),
            "kierunek_studiow__rel": _qs_picker("kierunek_studiow", Kierunek_Studiow),
            "typ_odpowiedzialnosci__rel": _qs_picker(
                "typ_odpowiedzialnosci", Typ_Odpowiedzialnosci
            ),
        },
        Autor: {
            "tytul__rel": _qs_picker("tytul", Tytul),
            "aktualna_jednostka__rel": _dal_picker(
                "aktualna_jednostka",
                "bpp:jednostka-widoczna-autocomplete",
                ["nazwa", "skrot"],
            ),
        },
        Rekord: {
            "zrodlo__rel": _qs_picker("zrodlo", Zrodlo),
            "wydawca__rel": _qs_picker("wydawca", Wydawca, ["nazwa"]),
            "konferencja__rel": _qs_picker("konferencja", Konferencja, ["nazwa"]),
            "wydawnictwo_nadrzedne__rel": _qs_picker(
                "wydawnictwo_nadrzedne", Wydawnictwo_Zwarte, ["tytul_oryginalny"]
            ),
            "charakter_formalny__rel": _qs_picker(
                "charakter_formalny", Charakter_Formalny
            ),
            "typ_kbn__rel": _qs_picker("typ_kbn", Typ_KBN),
            "jezyk__rel": _qs_picker("jezyk", Jezyk),
            "status_korekty__rel": _qs_picker(
                "status_korekty", Status_Korekty, ["nazwa"]
            ),
            "openaccess_wersja_tekstu__rel": _qs_picker(
                "openaccess_wersja_tekstu", Wersja_Tekstu_OpenAccess
            ),
            "openaccess_licencja__rel": _qs_picker(
                "openaccess_licencja", Licencja_OpenAccess
            ),
            "openaccess_czas_publikacji__rel": _qs_picker(
                "openaccess_czas_publikacji", Czas_Udostepnienia_OpenAccess
            ),
        },
    }

    def get_fields(self, model):
        # Picker `<fk>__rel` to nazwa syntetyczna (nie ma jej w modelu) — trzeba
        # ją dorzucić do introspekcji, inaczej nie będzie zbudowana ani
        # podpowiedziana. Klucze mapy `autocomplete` to dokładnie te nazwy.
        fields = list(super().get_fields(model))
        fields += list(self.autocomplete.get(model, {}).keys())
        return fields


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


def _annotate_breakdown(node, is_root=True, on_zero_path=True):
    """Dodaje do każdego węzła drzewa rozbicia pole ``label`` (tekst albo None)
    — komunikat wskazujący realnego „winowajcę" zerowego wyniku.

    Idea: idziemy „ścieżką zera". Dziecko jest na ścieżce zera tylko jeśli SAMO
    ma 0 trafień — bo wtedy jego pustka propaguje się w górę przez AND (każdy
    zerowy operand zeruje AND) albo współtworzy puste OR. Zero pochłonięte przez
    NIEPUSTE OR (np. ``(A or B)`` które zwraca >0, mimo że B=0) NIE jest
    winowajcą — i nie dostaje etykiety (koniec z szumem na martwych gałęziach).

    Etykietę dostaje tylko NAJGŁĘBSZY węzeł na ścieżce zera (ten, poniżej
    którego nie ma już zera) — czyli realny powód pustki:
    - liść z 0 trafień → „warunek nie pasuje do niczego",
    - AND-przecięcie (każdy operand z osobna >0, ale razem 0) → etykieta na AND.

    Korzeń (główne zapytanie) NIE dostaje etykiety — i tak wiadomo, że ma 0 (po
    to renderujemy rozbicie). Liczone z samych ``count`` + struktury — bez
    polegania na rolach z djangoql.
    """
    children = node["children"]
    child_on_zero = [on_zero_path and c["count"] == 0 for c in children]
    is_deepest_zero = on_zero_path and node["count"] == 0 and not any(child_on_zero)
    label = None
    if is_deepest_zero and not is_root:
        if children:
            label = "każdy warunek z osobna coś zwraca, ale ich połączenie daje 0"
        else:
            label = "ten warunek nie pasuje do żadnego rekordu"
    node["label"] = label
    for child, czp in zip(children, child_on_zero, strict=True):
        _annotate_breakdown(child, is_root=False, on_zero_path=czp)
    return node


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
            queryset = apply_search(queryset, query, schema=BppZapytanieSchema)
            # Filtrowanie po relacjach "do wielu" (np. autorzy.autor.nazwisko)
            # tworzy JOIN, ktory zwielokrotnia ten sam rekord raz na kazdy
            # pasujacy wiersz powiazany. .distinct() zwija te duplikaty, zeby
            # liczba wynikow i lista byly zgodne z liczba unikalnych obiektow.
            queryset = queryset.distinct()
            count = queryset.count()
            paginator = Paginator(queryset, self.paginate_by)
            page_number = self.request.GET.get("page") or 1
            results_page = paginator.get_page(page_number)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            error = self._format_error(exc)

        if results_page is not None and model_key == MODEL_REKORD:
            self._attach_admin_urls(results_page)

        breakdown = None
        if error is None and count == 0:
            try:
                breakdown = explain_empty(
                    model.objects.all(), query, schema=BppZapytanieSchema
                )
            except (DjangoQLError, FieldError, ValidationError, ValueError):
                logger.exception(
                    "explain_empty zawiodlo dla zapytania %r (model=%s)",
                    query,
                    model_key,
                )
                breakdown = None
            if breakdown is not None:
                _annotate_breakdown(breakdown)

        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=error,
            model_key=model_key,
            query=query,
            breakdown=breakdown,
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
