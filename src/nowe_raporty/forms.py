# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError

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
    od_roku = forms.TypedChoiceField(
        choices=wez_lata,
        coerce=int,
        widget=autocomplete.ListSelect2(
            forward='obiekt',
            url="bpp:lata-autocomplete"
        )
    )

    do_roku = forms.TypedChoiceField(
        choices=wez_lata,
        coerce=int,
        widget=autocomplete.ListSelect2(
            forward='obiekt',
            url="bpp:lata-autocomplete"
        )
    )

    def clean(self):
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
            Fieldset('Wybierz parametry',
                     'obiekt',
                     'od_roku',
                     'do_roku'),
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
            url='bpp:public-autor-autocomplete')
    )
