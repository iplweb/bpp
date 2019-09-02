from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, ButtonHolder, Submit
from dal import autocomplete
from django import forms
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


class AutorRaportDyscyplinForm(forms.Form):
    obiekt = forms.ModelChoiceField(
        label="Autor",
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:public-autor-autocomplete')
    )

    rok = forms.IntegerField(initial=year_last_month)

    _export = forms.ChoiceField(
        label="Format wyjściowy",
        choices=OUTPUT_FORMATS,
        required=True
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
                    Column('rok', css_class='large-6 small-6'),
                ),
                Row(Column('_export'))
            ),
            ButtonHolder(
                Submit('submit', 'Pobierz raport', css_id='id_submit',
                       css_class="submit button"),
            ))

        super(AutorRaportDyscyplinForm, self).__init__(*args, **kwargs)
