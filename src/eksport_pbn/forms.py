# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit, Column, Row
from django import forms

from bpp.models.struktura import Wydzial
from eksport_pbn.models import PlikEksportuPBN


class EksportDoPBNForm(forms.ModelForm):
    class Meta:
        model = PlikEksportuPBN
        fields = ['wydzial', 'od_roku', 'do_roku', 'artykuly', 'ksiazki', 'rozdzialy', 'rodzaj_daty', 'od_daty',
                  'do_daty']

    def __init__(self, *args, **kw):
        super(EksportDoPBNForm, self).__init__(*args, **kw)

        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
                Fieldset(
                        u'Zamów eksport PBN',
                        Row(Column('wydzial')),
                        Row(Column('od_roku', css_class='small-6 large-6'),
                            Column('do_roku', css_class='small-6 large-6')),
                        Row(Column('artykuly', css_class='small-4 large-4'),
                            Column('ksiazki', css_class='small-4 large-4'),
                            Column('rozdzialy', css_class='small-4 large-4')),
                        'rodzaj_daty',
                        Row(
                                Column('od_daty', css_class='small-6 large-6'),
                                Column('do_daty', css_class='small-6 large-6'),
                        ),
                        Submit('submit', u'Zamów', css_id='id_submit')))
        self.helper = helper

        self.fields['wydzial'].queryset = Wydzial.objects.filter(widoczny=True)
