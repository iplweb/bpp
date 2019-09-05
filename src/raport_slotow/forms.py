from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, ButtonHolder, Submit
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from bpp.models import Autor


def year_last_month():
    now = timezone.now().date()
    if now.month >= 2:
        return now.year
    return now.year - 1


OUTPUT_FORMATS = [
    ('html', 'wyświetl w przeglądarce'),
    # ('xlsx', 'Microsoft Excel (XLSX)'),
]


class AutorRaportSlotowForm(forms.Form):
    obiekt = forms.ModelChoiceField(
        label="Autor",
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:public-autor-autocomplete')
    )

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
                Row(
                    Column('od_roku', css_class='large-6 small-6'),
                    Column('do_roku', css_class='large-6 small-6')
                ),
                Row(
                    Column('rok', css_class='large-6 small-6'),
                ),
                Row(Column('_export'))
            ),
            ButtonHolder(
                Submit('submit', 'Pobierz raport', css_id='id_submit',
                       css_class="submit button"),
            ))

        super(AutorRaportSlotowForm, self).__init__(*args, **kwargs)
