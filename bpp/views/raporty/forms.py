# -*- encoding: utf-8 -*-
# -*- encoding: utf-8 -*-

"""W tym pakiecie znajdują się procedury generujące raporty, które są dostępne
"od ręki" -- generowane za pomocą WWW"""
from crispy_forms.helper import FormHelper
from django import forms
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit, Hidden, Row, Column as F4Column
from django.core import validators
from django.core.exceptions import ValidationError

import autocomplete_light
from bpp.models import Wydzial


def ustaw_rok(rok, lata):
    lata = list(lata)
    try:
        rok.min_value = lata[0]
    except IndexError:
        pass

    try:
        rok.max_value = lata[-1]
        rok.initial = lata[-1]
    except IndexError:
        pass

    if rok.max_value is not None:
        rok.field.validators.append(validators.MaxValueValidator(rok.max_value))
    if rok.min_value is not None:
        rok.field.validators.append(validators.MinValueValidator(rok.min_value))

class KronikaUczelniForm(forms.Form):
    rok = forms.IntegerField()

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Kronika Uczelni',
                'rok',
                Hidden("report", "kronika-uczelni")
            ),
            ButtonHolder(
                Submit('submit', u'Zamów', css_class='button white')
            )
        )
        super(KronikaUczelniForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['rok'], lata)


class RaportOPI2012Form(forms.Form):
    wydzial = forms.ModelMultipleChoiceField(
        queryset=Wydzial.objects.all())
    od_roku = forms.IntegerField()
    do_roku = forms.IntegerField()

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#OPI2012"
        #self.helper.form_action = "./prepare/"
        self.helper.layout = Layout(
            Fieldset(
                'Raport OPI 2012',
                'wydzial',
                Row(
                    F4Column('od_roku', css_class='large-6 small-6'),
                    F4Column('do_roku', css_class='large-6 small-6')
                ),
                Hidden("report", "raport-opi-2012")
            ),
            ButtonHolder(
                Submit('submit', u'Zamów', css_class='button white')
            )
        )

        self.base_fields['wydzial'].widget.attrs['size'] = \
            Wydzial.objects.all().count()
        super(RaportOPI2012Form, self).__init__(*args, **kwargs)
        ustaw_rok(self['od_roku'], lata)
        ustaw_rok(self['do_roku'], lata)

    def clean(self):
        od_roku = self.cleaned_data.get('od_roku')
        do_roku = self.cleaned_data.get("do_roku")

        if od_roku > do_roku:
            raise ValidationError("Data w polu 'Do roku' musi być większa lub równa, jak w polu 'Od roku'.")


class RaportJednostekForm(forms.Form):
    jednostka = autocomplete_light.ModelChoiceField(
        'JednostkaAutocompleteJednostka')

    od_roku = forms.IntegerField()
    do_roku = forms.IntegerField()

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#RaportJednostek"

        #self.helper.form_action = "./prepare/"
        self.helper.layout = Layout(
            Fieldset(
                'Raport jednostek',
                Row(
                    F4Column('jednostka', css_class='large-12 small-12')
                ),
                Row(
                    F4Column('od_roku', css_class='large-6 small-6'),
                    F4Column('do_roku', css_class='large-6 small-6')
                ),
                Hidden("report", "raport-jednostek")
            ),
            ButtonHolder(
                Submit('submit', u'Przejdź do', css_class='button white')
            )
        )

        super(RaportJednostekForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['od_roku'], lata)
        ustaw_rok(self['do_roku'], lata)


class RaportDlaKomisjiCentralnejForm(forms.Form):
    autor = autocomplete_light.ModelChoiceField(
        'AutorAutocompleteAutor')

    rok_habilitacji = forms.IntegerField(required=False)

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#RaportDlaKomisjiCentralnej"
        #self.helper.form_action = "./prepare/"
        self.helper.layout = Layout(
            Fieldset(
                'Raport dla Komisji Centralnej',
                'autor',
                'rok_habilitacji',
                Hidden("report", "raport-dla-komisji-centralnej")
            ),
            ButtonHolder(
                Submit('submit', u'Zamów', css_class='button white')
            )
        )

        super(RaportDlaKomisjiCentralnejForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['rok_habilitacji'], lata)
