# -*- encoding: utf-8 -*-

from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit, Field
from django.forms import ModelForm, FileField
from integrator.models import AutorIntegrationFile


class DodajPlik(ModelForm):
    file = FileField()
    class Meta:
        model = AutorIntegrationFile
        fields = ["file"]

    def __init__(self, *args, **kwargs):
        super(DodajPlik, self).__init__(*args, **kwargs)
        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                u'Dodaj plik',
                'file',
                Submit('submit', u'Wyślij', css_id='id_submit')))
        self.helper = helper
