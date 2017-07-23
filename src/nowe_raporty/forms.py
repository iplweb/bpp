# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit
from dal import autocomplete
from django import forms

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


class BaseRaportForm(forms.Form):
    rok = forms.TypedChoiceField(
        choices=wez_lata,
        coerce=int,
        widget=autocomplete.ListSelect2
    )

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = '.'
        self.helper.layout = Layout(
            Fieldset('Wybierz parametry',
                     'obiekt',
                     'rok'),
            ButtonHolder(
                Submit('submit', 'Pobierz raport', css_id='id_submit',
                       css_class="submit button"),
            ))

        super(BaseRaportForm, self).__init__(*args, **kwargs)


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
            url='bpp:autor-autocomplete')
    )
