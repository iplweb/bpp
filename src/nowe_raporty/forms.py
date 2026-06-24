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

    _export = forms.ChoiceField(
        label="Format wyjściowy", choices=OUTPUT_FORMATS, required=True
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
        required=False, label="Tylko prace punktowane (pkt MNiSW > 0)"
    )

    # nazwy pól zaawansowanych przekazywanych w querystringu do widoku generuj
    POLA_ZAAWANSOWANE = [
        "punkty_mnisw_od",
        "punkty_mnisw_do",
        "if_od",
        "if_do",
        "punktacja_wewnetrzna_od",
        "punktacja_wewnetrzna_do",
        "tylko_punktowane",
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

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

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
                Row(Column("_export")),
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
            *self._grupa_zakres("Punkty MNiSW", "punkty_mnisw_od", "punkty_mnisw_do"),
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


def form_class_dla(definicja):
    """Dynamiczna klasa formularza per DefinicjaRaportu.

    formdefaults kluczuje zapisane domyślne wartości po ``full_name`` =
    ``"{module}.{ClassName}"`` (bez hooka do override). Jedna wspólna klasa →
    kolizja defaultów między raportami. Dlatego budujemy klasę o STABILNYM,
    unikalnym ``__name__``/``__module__`` wyprowadzonym ze sluga.
    """
    import re

    from .poziomy import POZIOMY

    cfg = POZIOMY[definicja.poziom]
    pole = cfg.pole_obiektu()
    attrs = {"__module__": "nowe_raporty.forms_dynamiczne"}
    if pole is not None:
        attrs["obiekt"] = pole
        attrs["OBJ_FIELD"] = Row(Column("obiekt"))
    else:
        attrs["OBJ_FIELD"] = ""

    nazwa = "RaportForm_" + re.sub(r"\W", "_", definicja.slug)
    # użyj metaklasy formularza (DeclarativeFieldsMetaclass), nie gołego type -
    # inaczej "metaclass conflict" i pole 'obiekt' nie trafiłoby do base_fields.
    metaklasa = type(BaseRaportForm)
    return metaklasa(nazwa, (BaseRaportForm,), attrs)
