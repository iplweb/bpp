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
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.aggregates import Max, Min

from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka, Wydzial
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
    punkty_mnisw_od = forms.FloatField(required=False, label="Punkty MNiSW od")
    punkty_mnisw_do = forms.FloatField(required=False, label="Punkty MNiSW do")
    if_od = forms.FloatField(required=False, label="Impact Factor od")
    if_do = forms.FloatField(required=False, label="Impact Factor do")
    punktacja_wewnetrzna_od = forms.FloatField(
        required=False, label="Punktacja wewnętrzna od"
    )
    punktacja_wewnetrzna_do = forms.FloatField(
        required=False, label="Punktacja wewnętrzna do"
    )
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        uczelnia = Uczelnia.objects.get_default()
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
                formdefaults_html_after(self),
            ),
            HTML(
                '<details class="opcje-zaawansowane hide-for-print" '
                'style="margin-bottom: 1rem;"><summary>Opcje zaawansowane</summary>'
            ),
            *self._wiersze_zaawansowane(),
            HTML("</details>"),
            ButtonHolder(
                Submit(
                    "submit",
                    "Pobierz raport",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )

    def _wiersze_zaawansowane(self):
        wiersze = [
            Row(
                Column("punkty_mnisw_od", css_class="large-6 medium-6 small-12"),
                Column("punkty_mnisw_do", css_class="large-6 medium-6 small-12"),
            ),
            Row(
                Column("if_od", css_class="large-6 medium-6 small-12"),
                Column("if_do", css_class="large-6 medium-6 small-12"),
            ),
        ]
        if "punktacja_wewnetrzna_od" in self.fields:
            wiersze.append(
                Row(
                    Column(
                        "punktacja_wewnetrzna_od",
                        css_class="large-6 medium-6 small-12",
                    ),
                    Column(
                        "punktacja_wewnetrzna_do",
                        css_class="large-6 medium-6 small-12",
                    ),
                )
            )
        wiersze.append(Row(Column("tylko_punktowane")))
        return wiersze

        lata = Rekord.objects.all().aggregate(Min("rok"), Max("rok"))
        for field in self["od_roku"], self["do_roku"]:
            if lata["rok__min"] is not None:
                field.field.validators.append(MinValueValidator(lata["rok__min"]))
            if lata["rok__max"] is not None:
                field.field.validators.append(MaxValueValidator(lata["rok__max"]))


class UczelniaRaportForm(BaseRaportForm):
    OBJ_FIELD = ""

    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace afiliowane",
        help_text="Odznaczenie tego pola uwzględnia w raporcie rekordy "
        "w których autor przypisany jest do jednostki uczelni, ale nie afiliuje na nią",
        required=False,
    )


class WydzialRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Wydział",
        queryset=Wydzial.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:wydzial-autocomplete",
            attrs={"class": "bpp-autocomplete-wide"},
        ),
    )

    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace afiliowane",
        help_text="Odznaczenie tego pola uwzględnia w raporcie rekordy "
        "w których autor przypisany jest do jednostki z wybranego wydziału, ale nie afiliuje na nią",
        required=False,
    )


class JednostkaRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Jednostka",
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace afiliowane",
        help_text="Odznaczenie tego pola uwzględnia w raporcie rekordy "
        "w których autor przypisany jest do wybranej jednostki, ale nie afiliuje na nią",
        required=False,
    )


class AutorRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Autor",
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:public-autor-autocomplete"),
    )

    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace z afiliacją uczelni",
        help_text="Odznaczenie tego pola uwzględnia w raporcie rekordy "
        "w których autor przypisany jest do jednostek "
        "pozauczelnianych (obcych).",
        required=False,
    )


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
