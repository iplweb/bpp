from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from djangoql.admin import DjangoQLSearchMixin

from pbn_api.models import Publisher

from django.contrib import admin

from bpp.admin.filters import PBN_UID_IDObecnyFilter
from bpp.const import PBN_UID_LEN
from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Poziom_WydawcyInlineForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        if kw.get("instance"):
            self.fields["rok"].disabled = True

    def clean(self):
        if (
            "wydawca" in self.cleaned_data
            and self.cleaned_data["wydawca"].alias_dla_id is not None
        ):
            raise ValidationError("Nie można przypisywac poziomu wydawcy dla aliasów")
        return self.cleaned_data


class Poziom_WydawcyInline(admin.TabularInline):
    model = Poziom_Wydawcy
    form = Poziom_WydawcyInlineForm
    extra = 1


class MaAliasListFilter(admin.SimpleListFilter):
    title = "ma alias"
    parameter_name = "ma_alias"

    def lookups(self, request, model_admin):
        return [
            ("0", "nie"),
            ("1", "tak"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(alias_dla=None)
        elif self.value() == "1":
            return queryset.exclude(alias_dla=None)


class WydawcaForm(forms.ModelForm):
    pbn_uid = forms.ModelChoiceField(
        required=False,
        queryset=Publisher.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:publisher-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )

    alias_dla = forms.ModelChoiceField(
        required=False,
        queryset=Wydawca.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="bpp:wydawca-autocomplete", attrs=dict(style="width: 746px;")
        ),
    )


@admin.register(Wydawca)
class WydawcaAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    form = WydawcaForm

    search_fields = [
        "nazwa",
        "alias_dla__nazwa",
        "pbn_uid__mongoId",
        "alias_dla__pbn_uid__mongoId",
    ]
    autocomplete_fields = [
        "alias_dla",
    ]

    list_display = [
        "nazwa",
        "alias_dla",
        "ile_aliasow",
        "poziomy_wydawcy",
        "pbn_uid_id",
    ]
    list_filter = [MaAliasListFilter, PBN_UID_IDObecnyFilter]
    inlines = [
        Poziom_WydawcyInline,
    ]

    MIN_TRIGRAM_MATCH = 0.1

    def ile_aliasow(self, obj):
        if obj.ile_aliasow:
            return obj.ile_aliasow
        return

    def poziomy_wydawcy(self, obj):
        if obj.lista_poziomow:
            return "określone"

    def get_search_results(self, request, queryset, search_term):
        if self.search_mode_toggle_enabled() and self.djangoql_search_enabled(request):
            return DjangoQLSearchMixin.get_search_results(
                self, request, queryset, search_term
            )

        if not search_term or (
            len(search_term) == PBN_UID_LEN and search_term.find(" ") == -1
        ):
            return super().get_search_results(request, queryset, search_term)

        return super().get_search_results(request, queryset, search_term)
        # queryset = (
        #     queryset.annotate(similarity=TrigramSimilarity("nazwa", search_term))
        #     .filter(similarity__gte=self.MIN_TRIGRAM_MATCH)
        #     .order_by("-similarity")
        # )
        # return queryset, False
