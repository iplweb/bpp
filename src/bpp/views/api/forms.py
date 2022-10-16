from django import forms

from bpp.forms.fields import ORCIDField
from bpp.models import Autor, Rekord


class UstawORCIDAutoraForm(forms.Form):
    autor = forms.ModelChoiceField(queryset=Autor.objects.all())

    orcid = ORCIDField()


class UstawStronyRekorduForm(forms.Form):
    rekord = forms.ModelChoiceField(queryset=Rekord.objects.all())
    strony = forms.CharField(max_length=512)


class UstawTomRekorduForm(forms.Form):
    rekord = forms.ModelChoiceField(queryset=Rekord.objects.all())
    tom = forms.CharField(max_length=512)


class UstawNrZeszytuRekorduForm(forms.Form):
    rekord = forms.ModelChoiceField(queryset=Rekord.objects.all())
    nr_zeszytu = forms.CharField(max_length=512)


class UstawStreszczenieRekorduForm(forms.Form):
    rekord = forms.ModelChoiceField(queryset=Rekord.objects.all())
    streszczenie = forms.CharField(max_length=10240)
