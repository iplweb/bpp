from django import forms

from django.contrib import admin

from bpp.admin.filters import PBN_UID_IDObecnyFilter
from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Poziom_WydawcyInlineForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kw):
        super(Poziom_WydawcyInlineForm, self).__init__(*args, **kw)
        if kw.get("instance"):
            self.fields["rok"].disabled = True


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


@admin.register(Wydawca)
class WydawcaAdmin(admin.ModelAdmin):
    search_fields = [
        "nazwa",
        "alias_dla__nazwa",
    ]
    autocomplete_fields = ["alias_dla", "pbn_uid"]
    list_display = ["nazwa", "alias_dla", "pbn_uid_id"]
    list_filter = [MaAliasListFilter, PBN_UID_IDObecnyFilter]
    inlines = [
        Poziom_WydawcyInline,
    ]
