from dal import autocomplete
from django import forms
from django.db.models import Q
from djangoql.admin import DjangoQLSearchMixin

from dynamic_columns.mixins import DynamicColumnsMixin
from ewaluacja2021.models import IloscUdzialowDlaAutora
from pbn_api.models import Scientist
from ..models import (  # Publikacja_Habilitacyjna
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Jednostka,
)
from .core import BaseBppAdminMixin
from .filters import (
    JednostkaFilter,
    OrcidObecnyFilter,
    PBN_UID_IDObecnyFilter,
    PBNIDObecnyFilter,
)
from .helpers import ADNOTACJE_FIELDSET, CHARMAP_SINGLE_LINE, ZapiszZAdnotacjaMixin
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin

from django.contrib import admin

# Proste tabele

# Autor_Dyscyplina


class IloscUdzialowDlaAutoraInline(admin.TabularInline):
    model = IloscUdzialowDlaAutora
    extra = 1
    fields = ["dyscyplina_naukowa", "ilosc_udzialow", "ilosc_udzialow_monografie"]

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        dyscypliny_autora = Autor_Dyscyplina.objects.filter(autor=obj).values(
            "dyscyplina_naukowa_id",
        )
        subdyscypliny_autora = (
            Autor_Dyscyplina.objects.filter(autor=obj)
            .exclude(subdyscyplina_naukowa=None)
            .values(
                "subdyscyplina_naukowa_id",
            )
        )
        formset.form.base_fields[
            "dyscyplina_naukowa"
        ].queryset = Dyscyplina_Naukowa.objects.filter(
            Q(pk__in=dyscypliny_autora) | Q(pk__in=subdyscypliny_autora)
        )

        return formset


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
        super().__init__(*args, **kw)
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
    pbn_uid = forms.ModelChoiceField(
        label="Odpowiednik w PBN",
        required=False,
        queryset=Scientist.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:scientist-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    class Meta:
        fields = "__all__"
        model = Autor
        widgets = {"imiona": CHARMAP_SINGLE_LINE, "nazwisko": CHARMAP_SINGLE_LINE}


class AutorAdmin(
    DjangoQLSearchMixin,
    ZapiszZAdnotacjaMixin,
    EksportDanychMixin,
    BaseBppAdminMixin,
    DynamicColumnsMixin,
    admin.ModelAdmin,
):
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    max_allowed_export_items = 5000

    form = AutorForm
    autocomplete_fields = ["pbn_uid"]
    resource_class = resources.AutorResource

    list_display_always = ["nazwisko", "imiona"]

    list_display_default = [
        "tytul",
        "pseudonim",
        "poprzednie_nazwiska",
        "email",
        "pbn_id",
        "orcid",
        "pbn_uid_id",
    ]

    list_display_allowed = [
        "id",
        "ostatnio_zmieniony",
        "adnotacje",
        "aktualna_jednostka",
        "aktualna_funkcja",
        "pokazuj",
        "www",
        "plec",
        "urodzony",
        "zmarl",
        "pokazuj_poprzednie_nazwiska",
        "orcid_w_pbn",
        "system_kadrowy_id",
    ]

    list_select_related = {
        "tytul": [
            "tytul",
        ],
        "aktualna_jednostka": ["aktualna_jednostka", "aktualna_jednostka__wydzial"],
        "aktualna_funkcja": ["aktualna_funkcja"],
    }

    fields = None
    inlines = [
        Autor_JednostkaInline,
        Autor_DyscyplinaInline,
        IloscUdzialowDlaAutoraInline,
    ]
    list_filter = [
        JednostkaFilter,
        "aktualna_jednostka__wydzial",
        "tytul",
        PBNIDObecnyFilter,
        OrcidObecnyFilter,
        PBN_UID_IDObecnyFilter,
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
        "system_kadrowy_id",
        "orcid",
        "aktualna_jednostka__nazwa",
    ]
    readonly_fields = ["ostatnio_zmieniony", "aktualna_jednostka"]

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
                    "orcid_w_pbn",
                    "pbn_id",
                    "pbn_uid",
                    "system_kadrowy_id",
                    "aktualna_jednostka",
                )
            },
        ),
        (
            "Biografia",
            {
                "classes": ("grp-collapse grp-closed",),
                "fields": (
                    "urodzony",
                    "zmarl",
                    "poprzednie_nazwiska",
                    "pokazuj_poprzednie_nazwiska",
                ),
            },
        ),
        ADNOTACJE_FIELDSET,
    )


admin.site.register(Autor, AutorAdmin)
