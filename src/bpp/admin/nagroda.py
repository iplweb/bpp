# -*- encoding: utf-8 -*-

from dal import autocomplete
from django import forms
from django.contrib.contenttypes.admin import GenericTabularInline, GenericStackedInline

from bpp.models.nagroda import Nagroda, OrganPrzyznajacyNagrody


class NagrodaForm(forms.ModelForm):
    organ_przyznajacy = forms.ModelChoiceField(
        queryset=OrganPrzyznajacyNagrody.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='bpp:organ-przyznajacy-nagrody-autocomplete')
    )

    class Meta:
        fields = ["nazwa",
                  "organ_przyznajacy",
                  "rok_przyznania",
                  "uzasadnienie",
                  "adnotacja"]
        model = Nagroda


class NagrodaInline(GenericStackedInline):
    model = Nagroda
    extra = 0
    form = NagrodaForm
