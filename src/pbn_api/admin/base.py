# Register your models here.


from django.db import models

# class JsonAdmin(admin.ModelAdmin):
from .mixins import ReadOnlyListChangeFormAdminMixin
from .widgets import PrettyJSONWidgetReadonly

from django.contrib import admin


class BasePBNAPIAdminNoReadonly(admin.ModelAdmin):
    list_per_page = 25
    formfield_overrides = {models.JSONField: {"widget": PrettyJSONWidgetReadonly}}


class BasePBNAPIAdmin(ReadOnlyListChangeFormAdminMixin, BasePBNAPIAdminNoReadonly):
    pass


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
