# -*- encoding: utf-8 -*-

from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit
from crispy_forms_foundation.layout import Row, Column
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.aggregates import Min, Max
from django.utils import timezone
from django.utils.safestring import mark_safe

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Wydzial, Jednostka


def wez_lata():
    lata = Rekord.objects.all() \
        .values_list('rok', flat=True) \
        .distinct() \
        .order_by('-rok')
    return zip(lata, lata)


wybory = ["wydzial", "jednostka", "autor"]

OUTPUT_FORMATS = [
    ('html', 'wyświetl w przeglądarce'),
    ('docx', 'Microsoft Word (DOCX)'),
    ('xlsx', 'Microsoft Excel (XLSX)'),
]


def year_last_month():
    now = timezone.now().date()
    if now.month >= 2:
        return now.year
    return now.year - 1

class BaseRaportForm(forms.Form):
    od_roku = forms.IntegerField(initial=year_last_month)
    do_roku = forms.IntegerField(initial=year_last_month)

    _export = forms.ChoiceField(
        label="Format wyjściowy",
        choices=OUTPUT_FORMATS,
        required=True
    )

    def clean(self):
        if 'od_roku' in self.cleaned_data and 'do_roku' in self.cleaned_data:
            if self.cleaned_data['od_roku'] > self.cleaned_data['do_roku']:
                raise ValidationError(
                    {"od_roku": ValidationError(
                        'Pole musi być większe lub równe jak pole "Do roku".')
                    }
                )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = '.'
        self.helper.layout = Layout(
            Fieldset(
                'Wybierz parametry',
                Row(Column('obiekt')),
                Row(
                    Column('od_roku', css_class='large-6 small-6'),
                    Column('do_roku', css_class='large-6 small-6')
                ),
                Row(Column('_export'))
            ),
            ButtonHolder(
                Submit('submit', 'Pobierz raport', css_id='id_submit',
                       css_class="submit button"),
            ))

        super(BaseRaportForm, self).__init__(*args, **kwargs)

        lata = Rekord.objects.all().aggregate(Min('rok'), Max('rok'))
        for field in self['od_roku'], self['do_roku']:
            if lata['rok__min'] is not None:
                field.field.validators.append(MinValueValidator(lata['rok__min']))
            if lata['rok__max'] is not None:
                field.field.validators.append(MaxValueValidator(lata['rok__max']))

class WydzialRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Wydział",
        queryset=Wydzial.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:wydzial-autocomplete',
            attrs=dict(style="width: 746px;")
        )
    )


class JednostkaRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Jednostka",
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:jednostka-autocomplete')
    )


class AutorRaportForm(BaseRaportForm):
    obiekt = forms.ModelChoiceField(
        label="Autor",
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:public-autor-autocomplete')
    )

    tylko_z_jednostek_uczelni = forms.BooleanField(
        initial=True,
        label="Tylko prace z jednostek uczelni",
        help_text="Odznaczenie tego pola uwzględnia w raporcie rekordy "
                  "w których autor przypisany jest do jednostek "
                  "pozauczelnianych (obcych).",
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(AutorRaportForm, self).__init__(*args, **kwargs)

        self.helper.layout = Layout(
            Fieldset(
                'Wybierz parametry',
                Row(Column('obiekt')),
                Row(
                    Column('od_roku', css_class='large-6 medium-6 small-12'),
                    Column('do_roku', css_class='large-6 medium-6 small-12')
                ),
                Row(Column('_export')),
                Row(Column('tylko_z_jednostek_uczelni')),
            ),
            ButtonHolder(
                Submit('submit',
                       'Pobierz raport',
                       css_id='id_submit',
                       css_class="submit button"),
            ))
