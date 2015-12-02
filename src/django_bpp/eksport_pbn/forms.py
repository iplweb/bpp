# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit

from django import forms
from bpp.models.struktura import Wydzial
from eksport_pbn.models import PlikEksportuPBN


class EksportDoPBNForm(forms.ModelForm):
    class Meta:
        model = PlikEksportuPBN
        fields = ['wydzial', 'rok', 'artykuly', 'ksiazki', 'rozdzialy', 'rodzaj_daty', 'data']


    def __init__(self, *args, **kw):
        super(EksportDoPBNForm, self).__init__(*args, **kw)

        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                u'Zamów eksport PBN',
                'wydzial', 'rok', 'artykuly', 'ksiazki', 'rozdzialy',
                'rodzaj_daty', 'data',
                Submit('submit', u'Zamów', css_id='id_submit')))
        self.helper = helper

        self.fields['wydzial'].queryset = Wydzial.objects.filter(widoczny=True)
