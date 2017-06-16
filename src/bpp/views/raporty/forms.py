# -*- encoding: utf-8 -*-
# -*- encoding: utf-8 -*-

"""W tym pakiecie znajdują się procedury generujące raporty, które są dostępne
"od ręki" -- generowane za pomocą WWW"""
import autocomplete_light
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit, Hidden, Row, Column as F4Column
from django import forms
from django.core import validators

from bpp.models import Wydzial


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


class RaportJednostekForm(forms.Form):
    jednostka = autocomplete_light.forms.ModelChoiceField(
        'RaportyJednostkaWidoczna')

    od_roku = forms.IntegerField()
    do_roku = forms.IntegerField()
    output = forms.BooleanField(label="Pobierz jako plik Microsoft Word", required=False)

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#RaportJednostek"

        # self.helper.form_action = "./prepare/"
        self.helper.layout = Layout(
            Fieldset(
                'Raport jednostek',
                Row(F4Column('jednostka', css_class='large-12 small-12')),
                Row(F4Column('od_roku', css_class='large-6 small-6'),
                    F4Column('do_roku', css_class='large-6 small-6')),
                Row(F4Column('output', css_class='large-12 small-12')),
                Hidden("report", "raport-jednostek")
            ),
            ButtonHolder(
                Submit('submit', u'Wyświetl', css_class='button white')
            )
        )

        super(RaportJednostekForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['od_roku'], lata)
        ustaw_rok(self['do_roku'], lata)


class RaportAutorowForm(forms.Form):
    autor = autocomplete_light.forms.ModelChoiceField(
        'AutorAutocompleteAutor')

    od_roku = forms.IntegerField()
    do_roku = forms.IntegerField()
    output = forms.BooleanField(label="Pobierz jako plik Microsoft Word", required=False)

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#RaportAutorow"

        # self.helper.form_action = "./prepare/"
        self.helper.layout = Layout(
            Fieldset(
                u'Raport autorów',
                Row(F4Column('autor', css_class='large-12 small-12')),
                Row(F4Column('od_roku', css_class='large-6 small-6'),
                    F4Column('do_roku', css_class='large-6 small-6')),
                Row(F4Column("output", css_class="large-12 small-12")),
                Hidden("report", "raport-autorow")
            ),
            ButtonHolder(
                Submit('submit', u'Szukaj', css_class='button white')
            )
        )

        super(RaportAutorowForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['od_roku'], lata)
        ustaw_rok(self['do_roku'], lata)


class RaportDlaKomisjiCentralnejForm(forms.Form):
    autor = autocomplete_light.forms.ModelChoiceField(
        'AutorAutocompleteAutor')

    rok_habilitacji = forms.IntegerField(required=False)

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_action = "#RaportDlaKomisjiCentralnej"
        # self.helper.form_action = "./prepare/"
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


class WydzialChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.nazwa


class RankingAutorowForm(forms.Form):
    wydzialy = WydzialChoiceField(
        label=u"Ogranicz do wydziału (wydziałów):",
        required=False,
        widget=forms.SelectMultiple(attrs={'size': '15'}),
        queryset=Wydzial.objects.filter(widoczny=True, zezwalaj_na_ranking_autorow=True),
        help_text=u"Jeżeli nie wybierzesz żadnego wydziału, system wygeneruje "
                  u"dane dla wszystkich wydziałów. Przytrzymaj przycisk CTRL ("
                  u"CMD na Maku) gdy klikasz, aby wybrać więcej, niż jeden "
                  u"wydział lub odznaczyć już zaznaczony wydział. ")

    od_roku = forms.IntegerField()
    do_roku = forms.IntegerField()

    def __init__(self, lata, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'

        self.helper.layout = Layout(
            Fieldset(
                u'Ranking autorów',
                Row(
                    F4Column('od_roku', css_class='large-6 small-6'),
                    F4Column('do_roku', css_class='large-6 small-6'),
                ),
                Row(
                    F4Column('wydzialy', css_class='large-12 small-12')
                ),
                Hidden("report", "ranking-autorow")
            ),
            ButtonHolder(
                Submit('submit', u'Otwórz', css_class='button white')
            )
        )

        super(RankingAutorowForm, self).__init__(*args, **kwargs)
        ustaw_rok(self['od_roku'], lata)
        ustaw_rok(self['do_roku'], lata)
