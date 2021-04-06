# Register your models here.
import json

from django.db.models import BLANK_CHOICE_DASH
from django.forms import widgets

from pbn_api.models import (
    Conference,
    Institution,
    Journal,
    Publication,
    Publisher,
    Scientist,
)

from django.contrib import admin
from django.contrib.postgres.fields import JSONField


class PrettyJSONWidget(widgets.Textarea):
    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 60)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception:
            # logger.warning("Error while formatting JSON: {}".format(e))
            return super(PrettyJSONWidget, self).format_value(value)


# class JsonAdmin(admin.ModelAdmin):


class BaseMongoDBAdmin(admin.ModelAdmin):
    search_fields = ["versions"]
    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}
    list_filter = ["status", "verificationLevel"]
    readonly_fields = [
        "mongoId",
        "status",
        "verificationLevel",
        "verified",
        "created_on",
        "last_updated_on",
        # "versions",
    ]

    fields = readonly_fields + [
        "versions",
    ]

    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        return []

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request, queryset.filter(status="ACTIVE"), search_term
        )
        return queryset, use_distinct


@admin.register(Institution)
class InstitutionAdmin(BaseMongoDBAdmin):

    list_display = [
        "name",
        "addressCity",
        "addressStreet",
        "addressStreetNumber",
        "addressPostalCode",
        "polonUid",
        "website",
        "mongoId",
    ]


@admin.register(Conference)
class ConferenceAdmin(BaseMongoDBAdmin):
    list_display = [
        "fullName",
        "startDate",
        "endDate",
        "city",
        "country",
        "website",
        "mongoId",
    ]


@admin.register(Journal)
class JournalAdmin(BaseMongoDBAdmin):
    list_display = ["title", "issn", "eissn", "websiteLink", "mongoId"]


@admin.register(Publisher)
class PublisherAdmin(BaseMongoDBAdmin):
    list_display = ["publisherName", "mniswId", "mongoId"]


@admin.register(Scientist)
class ScientistAdmin(BaseMongoDBAdmin):
    list_display = [
        "lastName",
        "name",
        "tytul",
        "polonUid",
        "orcid",
        "currentEmploymentsInstitutionDisplayName",
        "mongoId",
    ]


@admin.register(Publication)
class PublicationAdmin(BaseMongoDBAdmin):
    list_display = ["title", "type", "volume", "year", "publicUri", "doi"]
