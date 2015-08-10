
from django.forms import ModelForm, FileField
from integrator.models import AutorIntegrationFile


class DodajPlik(ModelForm):
    file = FileField()
    class Meta:
        model = AutorIntegrationFile
        fields = ["file"]