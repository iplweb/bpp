# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit
from django import forms

from integrator2.models.lista_ministerialna import ListaMinisterialnaIntegration


class FormListaMinisterialna(forms.ModelForm):

    class Meta:
        model = ListaMinisterialnaIntegration
        fields = ['file', 'year']

    def __init__(self, *args, **kw):
        super(FormListaMinisterialna, self).__init__(*args, **kw)
        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                'Dodaj plik',
                'file', 'year',
                Submit('submit', 'Wyślij', css_id='id_submit')))
        self.helper = helper
