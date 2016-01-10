# -*- encoding: utf-8 -*-

from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, Submit, Field
from django.forms import IntegerField
from django.forms import ModelForm, FileField
from django.forms.widgets import HiddenInput
from datetime import datetime
from bpp.fields import YearField
from integrator2.models import IntegrationFile, INTEGRATOR_LISTA_MINISTERIALNA


class DodajPlik(ModelForm):
    file = FileField()

    class Meta:
        model = IntegrationFile
        fields = ["file", "type"]

    def __init__(self, *args, **kwargs):
        super(DodajPlik, self).__init__(*args, **kwargs)
        helper = FormHelper(self)
        helper.form_class = "custom"
        helper.layout = Layout(
            Fieldset(
                u'Dodaj plik',
                'file', 'type',
                Submit('submit', u'Wyślij', css_id='id_submit')))
        self.helper = helper

