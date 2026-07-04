# Register your models here.


from django.contrib import admin
from django.db import models

# class JsonAdmin(admin.ModelAdmin):
from .mixins import ReadOnlyListChangeFormAdminMixin
from .widgets import PrettyJSONWidgetReadonly


class BasePBNAPIAdminNoReadonly(admin.ModelAdmin):
    list_per_page = 25
    formfield_overrides = {models.JSONField: {"widget": PrettyJSONWidgetReadonly}}


class BasePBNAPIAdmin(ReadOnlyListChangeFormAdminMixin, BasePBNAPIAdminNoReadonly):
    pass


class InstytucjaColumnAdminMixin:
    """Warunkowa kolumna „Instytucja PBN".

    Pokazywana tylko gdy w systemie jest >1 uczelnia (instalacja
    multi-hosted). Pole źródłowe konfiguruje ``instytucja_pbn_field``:
    V1/Oświadczenia → ``institutionId`` (zawsze wypełnione), V2 → ``uczelnia``
    (V2 nie ma ``institutionId``). Na instalacji jednouczelnianej kolumna
    w ogóle się nie pojawia.
    """

    instytucja_pbn_field = "institutionId"

    def get_list_display(self, request):
        ld = list(super().get_list_display(request))
        from bpp.models import Uczelnia

        if Uczelnia.objects.count() > 1:
            ld = ld + ["instytucja_pbn"]
        return ld

    @admin.display(description="Instytucja PBN")
    def instytucja_pbn(self, obj):
        return getattr(obj, self.instytucja_pbn_field)


class BaseMongoDBAdmin(BasePBNAPIAdmin):
    search_fields = ["mongoId", "versions"]
    list_filter = ["status", "verificationLevel"]
    readonly_fields = [
        "mongoId",
        "status",
        "verificationLevel",
        "verified",
        "created_on",
        "last_updated_on",
    ]

    fields = readonly_fields + [
        "versions",
    ]

    # def get_search_results(self, request, queryset, search_term):
    #     queryset, use_distinct = super().get_search_results(
    #         request, queryset.exclude(status="DELETED"), search_term
    #     )
    #     return queryset, use_distinct
