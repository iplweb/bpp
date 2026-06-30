from django import forms

from demo.models import DemoImport


class DemoImportForm(forms.ModelForm):
    class Meta:
        model = DemoImport
        fields: list = []
