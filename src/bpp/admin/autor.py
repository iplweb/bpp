from dal import autocomplete
from django import forms
from djangoql.admin import DjangoQLSearchMixin

from dynamic_columns.mixins import DynamicColumnsMixin
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
from pbn_api.models import Scientist
from ..models import (  # Publikacja_Habilitacyjna
    Autor,
    Autor_Absencja,
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
from .helpers.fieldsets import ADNOTACJE_FIELDSET, ZapiszZAdnotacjaMixin
from .helpers.widgets import CHARMAP_SINGLE_LINE
from .xlsx_export import resources
from .xlsx_export.mixins import EksportDanychMixin

from django.contrib import admin

# Proste tabele

# Autor_Dyscyplina


class IloscUdzialowDlaAutoraZaRokInline(admin.TabularInline):
    model = IloscUdzialowDlaAutoraZaRok
    extra = 1
    fields = [
        "rok",
        "dyscyplina_naukowa",
        "ilosc_udzialow",
        "ilosc_udzialow_monografie",
    ]
    readonly_fields = fields

    def has_delete_permission(self, request, obj=...):
        return False

    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj=...):
        return False


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


class Autor_AbsencjaInline(admin.TabularInline):
    model = Autor_Absencja
    extra = 1
    fields = ("rok", "ile_dni")


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
        Autor_AbsencjaInline,
        IloscUdzialowDlaAutoraZaRokInline,
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

    def get_changeform_initial_data(self, request):
        """Get initial data for the main form and prepare inline data."""
        initial_data = super().get_changeform_initial_data(request)

        # Store inline initial data in request for later use in get_formset_kwargs
        inline_initial_data = self._prepare_inline_initial_data(request, initial_data)
        if inline_initial_data:
            if not hasattr(request, "_autor_inline_initial_data"):
                request._autor_inline_initial_data = {}
            request._autor_inline_initial_data.update(inline_initial_data)

        return initial_data

    def _prepare_inline_initial_data(self, request, main_initial_data):
        """
        Prepare initial data for inlines based on URL parameters or main form data.

        Handles the Django formset parameter format used by the "Utwórz w BPP" button
        from the scientist admin, such as:
        autor_dyscyplina_set-0-rok=2025
        autor_dyscyplina_set-0-dyscyplina_naukowa=55
        autor_dyscyplina_set-0-procent_dyscypliny=100.0
        autor_jednostka_set-0-jednostka=123

        Returns a dictionary with keys as inline prefixes and values as lists of
        initial data dictionaries for each inline form.
        """
        inline_data = {}

        # Parse Django formset parameters from GET request
        inline_data.update(self._parse_formset_parameters(request.GET))

        # Also support simple parameter format for backwards compatibility
        inline_data.update(self._parse_simple_parameters(request.GET))

        return inline_data

    def _parse_formset_parameters(self, get_params):
        """
        Parse Django formset parameters from GET request.

        Handles parameters like:
        autor_dyscyplina_set-0-rok=2025
        autor_dyscyplina_set-0-dyscyplina_naukowa=55
        autor_dyscyplina_set-0-procent_dyscypliny=100.0
        autor_jednostka_set-0-jednostka=123
        autor_jednostka_set-0-rozpoczal_prace=2024-01-01
        """
        import re
        from collections import defaultdict

        inline_data = defaultdict(list)
        formset_data = defaultdict(lambda: defaultdict(dict))

        # Pattern to match formset parameters: prefix-index-field
        formset_pattern = re.compile(r"^(autor_\w+_set)-(\d+)-(\w+)$")

        for key, value in get_params.items():
            match = formset_pattern.match(key)
            if match:
                prefix, index, field = match.groups()
                index = int(index)

                # Convert values to appropriate types
                converted_value = self._convert_formset_value(field, value)
                if converted_value is not None:
                    formset_data[prefix][index][field] = converted_value

        # Convert to the expected format: list of dictionaries
        for prefix, indexed_data in formset_data.items():
            # Sort by index and create list
            sorted_indices = sorted(indexed_data.keys())
            inline_data[prefix] = [indexed_data[i] for i in sorted_indices]

        return dict(inline_data)

    def _convert_formset_value(self, field_name, value):
        """Convert formset field values to appropriate Python types."""
        if not value:
            return None

        try:
            # Handle numeric fields
            if field_name in [
                "dyscyplina_naukowa",
                "subdyscyplina_naukowa",
                "jednostka",
                "rok",
                "tytul",
            ]:
                return int(value)
            elif field_name in [
                "procent_dyscypliny",
                "procent_subdyscypliny",
                "wymiar_etatu",
            ]:
                return float(value)
            elif field_name in ["rozpoczal_prace", "zakonczyl_prace"]:
                # Handle date fields
                from datetime import datetime

                return datetime.strptime(value, "%Y-%m-%d").date()
            else:
                # Return as string for other fields
                return value
        except (ValueError, TypeError):
            # If conversion fails, return the original value
            return value

    def _parse_simple_parameters(self, get_params):
        """
        Parse simple parameter format for backwards compatibility.

        Handles parameters like:
        jednostka=123
        dyscyplina_naukowa=456&rok=2024
        """
        inline_data = {}

        # Check for jednostka parameter
        jednostka_id = get_params.get("jednostka")
        if jednostka_id:
            try:
                inline_data["autor_jednostka_set"] = [{"jednostka": int(jednostka_id)}]
            except (ValueError, TypeError):
                pass

        # Check for dyscyplina parameter
        dyscyplina_id = get_params.get("dyscyplina_naukowa")
        rok = get_params.get("rok")
        if dyscyplina_id:
            try:
                dyscyplina_data = {"dyscyplina_naukowa": int(dyscyplina_id)}
                if rok:
                    try:
                        dyscyplina_data["rok"] = int(rok)
                    except (ValueError, TypeError):
                        pass
                inline_data["autor_dyscyplina_set"] = [dyscyplina_data]
            except (ValueError, TypeError):
                pass

        return inline_data

    def get_formset_kwargs(self, request, obj, inline, prefix):
        """Override to provide initial data for inlines."""
        kwargs = super().get_formset_kwargs(request, obj, inline, prefix)

        # Only set initial data for new objects (when obj.pk is None)
        if obj.pk is None and hasattr(request, "_autor_inline_initial_data"):
            inline_initial_data = request._autor_inline_initial_data.get(prefix, [])
            if inline_initial_data:
                kwargs["initial"] = inline_initial_data

        return kwargs


admin.site.register(Autor, AutorAdmin)
