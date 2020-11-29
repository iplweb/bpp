# -*- encoding: utf-8 -*-

from dal import autocomplete
from django.contrib import admin

from .core import CommitedModelAdmin
from .filters import (
    JednostkaFilter,
    PBNIDObecnyFilter,
    PeselMD5ObecnyFilter,
    OrcidObecnyFilter,
)
from .helpers import *
from ..models import (
    Jednostka,
    Autor,
    Autor_Jednostka,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
)  # Publikacja_Habilitacyjna


# Proste tabele

# Autor_Dyscyplina


class Autor_DyscyplinaInlineForm(forms.ModelForm):
    dyscyplina_naukowa = forms.ModelChoiceField(
        queryset=Dyscyplina_Naukowa.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:dyscyplina-autocomplete"),
    )

    subdyscyplina_naukowa = forms.ModelChoiceField(
        queryset=Dyscyplina_Naukowa.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:dyscyplina-autocomplete"),
        required=False,
    )

    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kw):
        super(Autor_DyscyplinaInlineForm, self).__init__(*args, **kw)
        if kw.get("instance"):
            self.fields["rok"].disabled = True


class Autor_DyscyplinaInline(admin.TabularInline):
    model = Autor_Dyscyplina
    form = Autor_DyscyplinaInlineForm
    extra = 1
    fields = (
        "rok",
        "rodzaj_autora",
        "wymiar_etatu",
        "dyscyplina_naukowa",
        "procent_dyscypliny",
        "subdyscyplina_naukowa",
        "procent_subdyscypliny",
    )


# Autor_Jednostka


class Autor_JednostkaInlineForm(forms.ModelForm):
    autor = forms.ModelChoiceField(
        queryset=Autor.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:autor-autocomplete"),
    )

    jednostka = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"),
    )

    class Meta:
        fields = "__all__"


class Autor_JednostkaInline(admin.TabularInline):
    model = Autor_Jednostka
    form = Autor_JednostkaInlineForm
    extra = 1


# Autorzy


class AutorForm(forms.ModelForm):
    class Meta:
        fields = "__all__"
        model = Autor
        widgets = {"imiona": CHARMAP_SINGLE_LINE, "nazwisko": CHARMAP_SINGLE_LINE}


class AutorAdmin(ZapiszZAdnotacjaMixin, CommitedModelAdmin):
    form = AutorForm

    list_display = [
        "nazwisko",
        "imiona",
        "tytul",
        "pseudonim",
        "poprzednie_nazwiska",
        "email",
        "pbn_id",
        "orcid",
    ]
    list_select_related = [
        "tytul",
    ]
    fields = None
    inlines = [Autor_JednostkaInline, Autor_DyscyplinaInline]
    list_filter = [
        JednostkaFilter,
        "aktualna_jednostka__wydzial",
        "tytul",
        PBNIDObecnyFilter,
        OrcidObecnyFilter,
        PeselMD5ObecnyFilter,
    ]
    search_fields = [
        "imiona",
        "nazwisko",
        "pseudonim",
        "poprzednie_nazwiska",
        "email",
        "www",
        "id",
        "pbn_id",
    ]
    readonly_fields = ("pesel_md5", "ostatnio_zmieniony")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "imiona",
                    "nazwisko",
                    "tytul",
                    "pseudonim",
                    "pokazuj",
                    "email",
                    "www",
                    "orcid",
                    "pbn_id",
                    "pesel_md5",
                )
            },
        ),
        (
            "Biografia",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": ("urodzony", "zmarl", "poprzednie_nazwiska"),
            },
        ),
        ADNOTACJE_FIELDSET,
    )


admin.site.register(Autor, AutorAdmin)
