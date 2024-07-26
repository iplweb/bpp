from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import ButtonHolder
from crispy_forms_foundation.layout import Column as F4Column
from crispy_forms_foundation.layout import Fieldset, Hidden, Layout, Row, Submit
from django import forms
from django.core import validators
from django_tables2.export.export import TableExport

from bpp.models import Uczelnia, Wydzial


def ustaw_rok(rok, lata):
    lata = list(lata)
    try:
        rok.field.min_value = lata[0]
    except IndexError:
        pass

    try:
        rok.field.max_value = lata[-1]
        rok.field.initial = lata[-2]
    except IndexError:
        pass

    if rok.field.max_value is not None:
        rok.field.validators.append(validators.MaxValueValidator(rok.field.max_value))
    if rok.field.min_value is not None:
        rok.field.validators.append(validators.MinValueValidator(rok.field.min_value))


class WydzialChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.nazwa


OUTPUT_FORMATS = [
    ("html", "wyświetl w przeglądarce"),
]

OUTPUT_FORMATS.extend(
    zip(
        list(TableExport.FORMATS.keys()),
        [x.upper() for x in list(TableExport.FORMATS.keys())],
    )
)


class RankingAutorowForm(forms.Form):
    wydzialy = WydzialChoiceField(
        label="Ogranicz do wydziału (wydziałów):",
        required=False,
        widget=forms.SelectMultiple(attrs={"size": "8"}),
        queryset=Wydzial.objects.filter(
            widoczny=True, zezwalaj_na_ranking_autorow=True
        ),
        help_text="Jeżeli nie wybierzesz żadnego wydziału, system wygeneruje "
        "dane dla wszystkich wydziałów. Przytrzymaj przycisk CTRL ("
        "CMD na Maku) gdy klikasz, aby wybrać więcej, niż jeden "
        "wydział lub odznaczyć już zaznaczony wydział. ",
    )

    rozbij_na_jednostki = forms.BooleanField(
        label="Rozbij punktację na jednostki i wydziały",
        required=False,
        initial=lambda: Uczelnia.objects.first().ranking_autorow_rozbij_domyslnie,
    )

    tylko_afiliowane = forms.BooleanField(
        label="Tylko prace afiliowane na jednostki uczelni",
        required=False,
        initial=False,
        help_text="Pokaż tylko prace, gdzie autor afiliował na jednostkę "
        "wchodzącą w struktury uczelni",
    )

    bez_nieaktualnych = forms.BooleanField(
        label="Bez nieaktualnych autorów",
        initial=True,
        required=False,
        help_text="""Nie pokazuj autorów, którzy nie mają określonego pola 'Aktualna jednostka'.""",
    )

    od_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)
    do_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)

    _export = forms.ChoiceField(
        label="Format wyjściowy", required=True, choices=OUTPUT_FORMATS
    )

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = "post"

        self.helper.layout = Layout(
            Fieldset(
                "Ranking autorów",
                Row(
                    F4Column("od_roku", css_class="large-6 small-6"),
                    F4Column("do_roku", css_class="large-6 small-6"),
                ),
                Row(F4Column("_export", css_class="large-12 small-12")),
                Row(F4Column("rozbij_na_jednostki", css_class="large-12 small-12")),
                Row(F4Column("tylko_afiliowane", css_class="large-12 small-12")),
                Row(F4Column("bez_nieaktualnych", css_class="large-12 small-12")),
                Row(F4Column("wydzialy", css_class="large-12 small-12")),
                Hidden("report", "ranking-autorow"),
            ),
            ButtonHolder(Submit("submit", "Otwórz", css_class="button white")),
        )

        super().__init__(*args, **kwargs)
