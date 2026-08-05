from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from bpp.models import Grant, Grant_Rekordu


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = [
        "nazwa_projektu",
        "numer_projektu",
        "rok",
        "zrodlo_finansowania",
        "projekt",
    ]
    search_fields = ["nazwa_projektu", "numer_projektu", "rok", "zrodlo_finansowania"]
    # Filtr po projekcie pozwala zobaczyć wszystkie numery grantów jednego
    # projektu, a przez pozycję „puste” — te jeszcze do niego nieprzypięte.
    list_filter = ["projekt"]
    autocomplete_fields = ["projekt"]


class Grant_RekorduForm(forms.ModelForm):
    class Meta:
        model = Grant_Rekordu
        fields = ["grant"]


class Grant_RekorduInline(GenericTabularInline):
    model = Grant_Rekordu
    extra = 0
    form = Grant_RekorduForm
