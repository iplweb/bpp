# -*- encoding: utf-8 -*-

from django import forms

from egeria.models.core import EgeriaImport


class EgeriaImportCreateForm(forms.ModelForm):
    class Meta:
        fields = ['uczelnia', 'file',]# 'od', 'do']
        model = EgeriaImport
        widgets = {
            'od': forms.DateInput,
            'do': forms.DateInput
        }
