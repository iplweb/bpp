import re

from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    HTML,
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.aggregates import Max, Min

from bpp.models import Uczelnia
from bpp.models.cache import Rekord
from bpp.util import formdefaults_html_after, formdefaults_html_before, year_last_month
from bpp.util.autor_spoza_uczelni import sprawdz_autora_raportu

from . import sortowanie as sortowanie_raportu
from .models import DefinicjaRaportu


def wez_lata():
    lata = (
        Rekord.objects.all().values_list("rok", flat=True).distinct().order_by("-rok")
    )
    return zip(lata, lata, strict=False)


wybory = ["wydzial", "jednostka", "autor"]

OUTPUT_FORMATS = [
    ("html", "wyświetl w przeglądarce"),
    ("docx", "Microsoft Word (DOCX)"),
    ("xlsx", "Microsoft Excel (XLSX)"),
]


class BaseRaportForm(forms.Form):
    od_roku = forms.IntegerField(initial=year_last_month)
    do_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)

    OBJ_FIELD = Row(Column("obiekt"))

    # Poziom raportu (``DefinicjaRaportu.POZIOM_*``) — ustawiany przez
    # ``form_class_dla`` na dynamicznej podklasie; steruje per-uczelnia
    # zawężaniem pola ``obiekt`` w ``__init__``.
    POZIOM = None

    _export = forms.ChoiceField(
        label="Format wyjściowy", choices=OUTPUT_FORMATS, required=True
    )

    # FD467: porządek spisu. Nie jest to filtr, więc stoi w głównym fieldsecie
    # obok formatu wyjściowego, a nie w "Opcjach zaawansowanych".
    sortowanie = forms.ChoiceField(
        label="Sortowanie",
        choices=sortowanie_raportu.WYBORY,
        initial=sortowanie_raportu.DOMYSLNE,
        required=True,
    )

    # Wspólny default; podklasy per-poziom mogą nadpisać label/help_text.
    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace afiliowane",
        required=False,
    )

    # Opcje zaawansowane (schowane domyślnie, filtrują cały raport).
    # Labele są krótkie ("od"/"do"), bo nazwę metryki niesie nagłówek grupy
    # renderowany w _grupa_zakres() — patrz układ "Opcje zaawansowane".
    punkty_mnisw_od = forms.FloatField(required=False, label="od")
    punkty_mnisw_do = forms.FloatField(required=False, label="do")
    if_od = forms.FloatField(required=False, label="od")
    if_do = forms.FloatField(required=False, label="do")
    punktacja_wewnetrzna_od = forms.FloatField(required=False, label="od")
    punktacja_wewnetrzna_do = forms.FloatField(required=False, label="do")
    tylko_punktowane = forms.BooleanField(
        required=False, label="Tylko prace punktowane (pkt MNiSW/MEiN > 0)"
    )

    # Nazwy pól przekazywanych w querystringu do widoku generującego. Lista
    # steruje WYŁĄCZNIE przekazywaniem — o wyglądzie decyduje ``Layout`` niżej,
    # dlatego jest tu ``sortowanie``, które w układzie stoi zupełnie gdzie
    # indziej niż filtry zaawansowane. (Stąd nazwa ``POLA_PRZEKAZYWANE``, a nie
    # dawna ``POLA_ZAAWANSOWANE``: ta druga sugerowała związek z sekcją "Opcje
    # zaawansowane", którego nigdy nie było.)
    POLA_PRZEKAZYWANE = [
        "punkty_mnisw_od",
        "punkty_mnisw_do",
        "if_od",
        "if_do",
        "punktacja_wewnetrzna_od",
        "punktacja_wewnetrzna_do",
        "tylko_punktowane",
        "sortowanie",
    ]

    def clean(self):
        if "od_roku" in self.cleaned_data and "do_roku" in self.cleaned_data:
            if self.cleaned_data["od_roku"] > self.cleaned_data["do_roku"]:
                raise ValidationError(
                    {
                        "od_roku": ValidationError(
                            'Pole musi być większe lub równe jak pole "Do roku".'
                        )
                    }
                )

    def clean_obiekt(self):
        obiekt = self.cleaned_data["obiekt"]
        if self.POZIOM == DefinicjaRaportu.POZIOM_AUTOR:
            # FD#640: raportu (sum punktów/metryk) dla autora spoza uczelni
            # nie przygotowujemy.
            sprawdz_autora_raportu(obiekt, self._uczelnia_requestu)
        return obiekt

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        # FD#640: uczelnia oglądającego do odrzucenia autora spoza uczelni
        # (``clean_obiekt``); bez requestu nikt nie jest „spoza uczelni”.
        self._uczelnia_requestu = (
            Uczelnia.objects.get_for_request(request) if request is not None else None
        )

        # FD#528: „Od roku"/„Do roku" mają w deklaracji wywoływalny ``initial``.
        # django-formdefaults nie umie go zapisać (nie-JSON) i przy KAŻDYM
        # kolejnym odświeżeniu reprezentacji formularza kasuje takie pole
        # z bazy — razem z zapisanymi „Moimi wartościami domyślnymi". Na
        # instancji podstawiamy więc gotowe liczby; formdefaults zapisuje je
        # jako auto-wartość systemową i sam odświeża, gdy zmieni się rok.
        for nazwa in ("od_roku", "do_roku"):
            pole = self.fields[nazwa]
            if callable(pole.initial):
                pole.initial = pole.initial()

        # Multi-hosted: uczelnię bierzemy WYŁĄCZNIE z requestu
        # (``request._uczelnia``, ustawiane przez SiteResolutionMiddleware wg
        # hosta). Bez requestu — post_migrate (nowe_raporty.apps.create_entries
        # → form_class(), user=None), introspekcja formdefaults, testy — uczelnia
        # = None. NIE szukamy „domyślnej" uczelni: taki byt NIE istnieje (realne
        # stany: brak / jedna / wiele). None-tolerant — pola opcjonalne znikają,
        # gdy nie ma uczelni z requestu albo nie pokazuje punktacji wewnętrznej.
        uczelnia = getattr(request, "_uczelnia", None)
        if not (uczelnia and uczelnia.pokazuj_punktacje_wewnetrzna):
            self.fields.pop("punktacja_wewnetrzna_od", None)
            self.fields.pop("punktacja_wewnetrzna_do", None)

        # Faza B (#438): gdy uczelnia UŻYWA wydziałów, pole „Jednostka" nie
        # może oferować korzeni (``parent IS NULL``) — to „wydziały", które
        # mają własny raport poziomu „wydział"; wybór korzenia dawałby raport
        # tylko z prac przypiętych bezpośrednio do niego (zwykle pusty).
        # Zawężamy queryset WALIDACYJNY i przełączamy picker na wariant
        # „nie-toplevel" — analogicznie do ranking_autorow.forms.
        if (
            self.POZIOM == DefinicjaRaportu.POZIOM_JEDNOSTKA
            and "obiekt" in self.fields
            and uczelnia is not None
            and uczelnia.uzywaj_wydzialow
        ):
            self.fields["obiekt"].queryset = self.fields["obiekt"].queryset.filter(
                parent__isnull=False
            )
            self.fields[
                "obiekt"
            ].widget.url = "bpp:public-jednostka-nietoplevel-autocomplete"

        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."

        self.helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                self.OBJ_FIELD,
                Row(
                    Column("od_roku", css_class="large-6 medium-6 small-12"),
                    Column("do_roku", css_class="large-6 medium-6 small-12"),
                ),
                Row(
                    Column("_export", css_class="large-6 medium-6 small-12"),
                    Column("sortowanie", css_class="large-6 medium-6 small-12"),
                ),
                Row(Column("tylko_z_jednostek_uczelni")),
                # "Opcje zaawansowane" jako rozwijana sekcja WEWNĄTRZ fieldsetu
                # (analogicznie do "Filtry ..." na ranking-autorow). Natywny
                # <details> daje zwijanie bez JS; CSS robi z <summary> pasek
                # akordeonu z markerem +/-. Sekcja MUSI być w fieldsecie -
                # patrz uwaga o box-sizing przy stylach .opcje-zaawansowane.
                HTML(
                    '<details class="opcje-zaawansowane hide-for-print">'
                    "<summary>Opcje zaawansowane</summary>"
                    '<div class="opcje-zaawansowane__body">'
                ),
                *self._wiersze_zaawansowane(),
                HTML("</div></details>"),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Pobierz raport",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

        lata = Rekord.objects.all().aggregate(Min("rok"), Max("rok"))
        for field in self["od_roku"], self["do_roku"]:
            if lata["rok__min"] is not None:
                field.field.validators.append(MinValueValidator(lata["rok__min"]))
            if lata["rok__max"] is not None:
                field.field.validators.append(MaxValueValidator(lata["rok__max"]))

    @staticmethod
    def _grupa_zakres(naglowek, pole_od, pole_do):
        """Nagłówek metryki + para pól od/do obok siebie (Opcje zaawansowane).

        Inputy zostają w jednym wierszu także na małych ekranach (small-6),
        bo zakres "od–do" czyta się jako jedna całość.
        """
        return [
            HTML(f'<div class="zaawansowane-grupa-naglowek">{naglowek}</div>'),
            Row(
                Column(pole_od, css_class="large-6 medium-6 small-6"),
                Column(pole_do, css_class="large-6 medium-6 small-6"),
            ),
        ]

    def _wiersze_zaawansowane(self):
        elementy = [
            *self._grupa_zakres(
                "Punkty MNiSW/MEiN", "punkty_mnisw_od", "punkty_mnisw_do"
            ),
            *self._grupa_zakres("Impact Factor", "if_od", "if_do"),
        ]
        if "punktacja_wewnetrzna_od" in self.fields:
            elementy += self._grupa_zakres(
                "Punktacja wewnętrzna",
                "punktacja_wewnetrzna_od",
                "punktacja_wewnetrzna_do",
            )
        elementy.append(Row(Column("tylko_punktowane")))
        return elementy


#: Moduł, pod którym "mieszkają" dynamiczne klasy formularzy raportów. Moduł
#: istnieje naprawdę (``nowe_raporty/forms_dynamiczne.py``) i odtwarza klasę
#: z nazwy — formdefaults importuje klasę po ``full_name`` w oknie
#: „Moje wartości domyślne" (FD#528).
MODUL_FORMULARZY_DYNAMICZNYCH = "nowe_raporty.forms_dynamiczne"


def nazwa_klasy_formularza(slug):
    """Nazwa dynamicznej klasy formularza dla ``DefinicjaRaportu.slug``."""
    return "RaportForm_" + re.sub(r"\W", "_", slug)


def form_class_dla(definicja):
    """Dynamiczna klasa formularza per DefinicjaRaportu.

    formdefaults kluczuje zapisane domyślne wartości po ``full_name`` =
    ``"{module}.{ClassName}"`` (bez hooka do override). Jedna wspólna klasa →
    kolizja defaultów między raportami. Dlatego budujemy klasę o STABILNYM,
    unikalnym ``__name__``/``__module__`` wyprowadzonym ze sluga.
    """
    from .poziomy import POZIOMY

    cfg = POZIOMY[definicja.poziom]
    pole = cfg.pole_obiektu()
    attrs = {
        "__module__": MODUL_FORMULARZY_DYNAMICZNYCH,
        "POZIOM": definicja.poziom,
    }
    if pole is not None:
        attrs["obiekt"] = pole
        attrs["OBJ_FIELD"] = Row(Column("obiekt"))
    else:
        attrs["OBJ_FIELD"] = ""

    nazwa = nazwa_klasy_formularza(definicja.slug)
    # użyj metaklasy formularza (DeclarativeFieldsMetaclass), nie gołego type -
    # inaczej "metaclass conflict" i pole 'obiekt' nie trafiłoby do base_fields.
    metaklasa = type(BaseRaportForm)
    return metaklasa(nazwa, (BaseRaportForm,), attrs)
